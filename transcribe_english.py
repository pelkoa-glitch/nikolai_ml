#!/usr/bin/env python3
"""
Скрипт для транскрибации английских слов через llama.cpp API.
Функции:
- Потоковая запись в кэш.
- Сохранение регистра букв.
- Вывод отправляемых слов в консоль.
- Увеличенный таймаут.
- НОВАЯ ФИЧА: Повторная обработка слов с латиницей в транскрипции.
"""
import re
import json
import sys
import time
import requests
from pathlib import Path
from tqdm import tqdm

# === НАСТРОЙКИ ===
INPUT_FILE = "source_text/source_text.txt"
OUTPUT_FILE = "source_text/source_text_for_tts.txt"
CACHE_FILE = "transcriptions_cache.json"

LLM_API_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"

REQUEST_TIMEOUT = 6000
MAX_RETRIES = 3  # Максимум попыток для "грязного" слова

def apply_case(original_word: str, target_word: str) -> str:
    if not original_word:
        return target_word
    if original_word.isupper():
        return target_word.upper()
    elif original_word[0].isupper():
        return target_word.capitalize()
    else:
        return target_word.lower()

def extract_unique_english_words(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    return list(set(words))

def is_pure_cyrillic(text: str) -> bool:
    """
    Проверяет, состоит ли текст ТОЛЬКО из стандартных русских букв, 
    пробелов и дефисов. Отсекает латиницу, IPA (ɛ, ð, ʃ), греческие (δ) и цифры.
    """
    # Разрешены: а-я, А-Я, ё, Ё, пробелы и дефисы
    return bool(re.match(r'^[а-яёА-ЯЁ\s\-]+$', text))

def load_existing_cache():
    if Path(CACHE_FILE).exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"✅ Загружено {len(data)} слов из кэша ({CACHE_FILE})")
                return data
        except Exception as e:
            print(f"⚠️ Ошибка чтения кэша: {e}. Начинаем заново.")
    return {}

def save_to_cache(transcriptions):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(transcriptions, f, ensure_ascii=False, indent=2)

def get_transcriptions_via_api(words, all_cache, is_retry=False):
    if not words:
        return {}, []
    
    words_to_process = [w for w in words if w not in all_cache]
    if not words_to_process:
        return {}, []

    words_preview = ", ".join(words_to_process)
    retry_label = " [ПОВТОРНАЯ ПОПЫТКА]" if is_retry else ""
    print(f"\n📤 Отправляем{retry_label} ({len(words_to_process)} слов): {words_preview}")
    
    words_list_str = ", ".join([f'"{w}"' for w in words_to_process])
    
    # Усиленный промпт для повторных попыток
    if is_retry:
        system_prompt = (
            "You are a strict phonetic transcriber. "
            "Task: Convert English words to Russian Cyrillic phonetics. "
            "STRICT RULES:\n"
            "1. Output ONLY raw JSON. No thinking, no reasoning.\n"
            "2. Values MUST contain ONLY Cyrillic letters (А-Я, а-я, Ё, ё).\n"
            "3. NEVER mix Latin and Cyrillic in the same word.\n"
            "4. BAD example: 'approach' -> 'апroach' (Contains Latin!), \
                'recontextualized'-> 'реконтекстуалайзед' (NOT 'реконтекстуализед'), \
                'infrastructure' -> 'инфрастракчер' (NOT 'инфраструктура').\n"
        
            "5. GOOD: 'approach' -> 'апроуч' (Only Cyrillic!)\n"
            "6. Transcribe sounds, do not translate meanings."
        )
    else:
        system_prompt = (
            "You are a strict phonetic transcriber. "
            "Task: Convert English words to Russian Cyrillic phonetics. "
            "STRICT RULES:\n"
            "1. Output ONLY raw JSON. No thinking, no reasoning.\n"
            "2. Values MUST contain ONLY Cyrillic letters (А-Я, а-я, Ё, ё).\n"
            "3. NEVER mix Latin and Cyrillic in the same word.\n"
            "4. BAD example: 'approach' -> 'апroach' (Contains Latin!), \
                'recontextualized'-> 'реконтекстуалайзед' (NOT 'реконтекстуализед'), \
                'infrastructure' -> 'инфрастракчер' (NOT 'инфраструктура').\n"
        
            "5. GOOD: 'approach' -> 'апроуч' (Only Cyrillic!)\n"
            "6. Transcribe sounds, do not translate meanings."
        )
    
    user_prompt = f"Transcribe to Russian phonetics (strictly Cyrillic only): {words_list_str}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
    }

    try:
        start_time = time.time()
        response = requests.post(LLM_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
        duration = time.time() - start_time
        
        print(f"⏱️ Время: {duration:.1f}с | Статус: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Ошибка сервера: {response.text[:200]}")
            return {}, words_to_process  # Возвращаем все слова как "плохие"
            
        api_response = response.json()
        
        if "choices" not in api_response or len(api_response["choices"]) == 0:
            print("❌ Нет choices в ответе")
            return {}, words_to_process

        message = api_response["choices"][0].get("message", {})
        raw_text = message.get("content", "")

        if not raw_text or not raw_text.strip():
            print("⚠️ Пустой content от модели")
            return {}, words_to_process

        # Поиск JSON
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            print(f"❌ JSON не найден. Ответ: {raw_text[:200]}")
            return {}, words_to_process
        
        json_str = raw_text[start_idx : end_idx + 1]
        
        try:
            new_transcriptions = json.loads(json_str)
            if not isinstance(new_transcriptions, dict):
                print(f"❌ Ответ не словарь")
                return {}, words_to_process
            
            # === КЛЮЧЕВАЯ ПРОВЕРКА: разделяем на хорошие и плохие ===
                        # === ЖЕСТКАЯ ПРОВЕРКА НА ЧИСТУЮ КИРИЛЛИЦУ ===
            good_transcriptions = {}
            dirty_words = []
            
            for eng_word, ru_transcription in new_transcriptions.items():
                # Проверяем на чистую кириллицу И на то, что это не прямой перевод
                if not is_pure_cyrillic(ru_transcription):
                    print(f"   ⚠️ Грязные символы (IPA/латиница/греч.): '{eng_word}' -> '{ru_transcription}'")
                    dirty_words.append(eng_word)
                elif ru_transcription.lower() in ['час', 'русский', 'да', 'нет', 'привет']: # Примеры частых переводов
                    print(f"   ⚠️ Модель перевела, а не транскрибировала: '{eng_word}' -> '{ru_transcription}'")
                    dirty_words.append(eng_word)
                else:
                    good_transcriptions[eng_word] = ru_transcription
            
            # Проверяем пропущенные слова
            for word in words_to_process:
                if word not in new_transcriptions:
                    print(f"   ⚠️ Пропущено слово: '{word}'")
                    dirty_words.append(word)
            
            # Сохраняем только хорошие транскрипции
            if good_transcriptions:
                all_cache.update(good_transcriptions)
                save_to_cache(all_cache)
            
            print(f"✅ УСПЕХ! Получено {len(good_transcriptions)} чистых слов за {duration:.1f}с.")
            if dirty_words:
                print(f"   🔄 Требуют повторной обработки: {len(dirty_words)} слов")
            
            return good_transcriptions, dirty_words
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            return {}, words_to_process
        
    except requests.exceptions.Timeout:
        print(f"\n⏳ ТАЙМАУТ ({REQUEST_TIMEOUT}с).")
        return {}, words_to_process
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        return {}, words_to_process

def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f"❌ Файл {INPUT_FILE} не найден!")
        sys.exit(1)
    
    print(f"📖 Читаю {INPUT_FILE}...")
    text = input_path.read_text(encoding="utf-8")
    
    unique_words = extract_unique_english_words(text)
    print(f"🔍 Найдено уникальных английских слов: {len(unique_words)}")
    
    if not unique_words:
        print("ℹ️ Английских слов нет. Копирую файл как есть.")
        import shutil
        shutil.copyfile(input_path, OUTPUT_FILE)
        return

    # 1. Загружаем кэш
    all_transcriptions = load_existing_cache()
    
    # 2. Список слов на обработку (изначально все уникальные слова)
    # Каждому слову присваиваем счетчик попыток
    retry_counts = {word: 0 for word in unique_words}
    
    # Исключаем уже обработанные слова
    remaining_words = [w for w in unique_words if w not in all_transcriptions]
    
    if not remaining_words:
        print("🎉 Все слова уже обработаны!")
    else:
        print(f"🚀 Осталось обработать: {len(remaining_words)} слов.")
        
        chunk_size = 50
        attempt_number = 0
        
        while remaining_words:
            attempt_number += 1
            print(f"\n{'='*60}")
            print(f"🔄 РАУНД {attempt_number} | Осталось слов: {len(remaining_words)}")
            print(f"{'='*60}")
            
            # Проверяем, не превышен ли лимит попыток для каких-то слов
            words_to_skip = [w for w in remaining_words if retry_counts[w] >= MAX_RETRIES]
            if words_to_skip:
                print(f"\n⚠️ Пропускаем {len(words_to_skip)} слов (превышен лимит {MAX_RETRIES} попыток):")
                for w in words_to_skip[:10]:  # Показываем первые 10
                    print(f"   - {w}")
                if len(words_to_skip) > 10:
                    print(f"   ... и еще {len(words_to_skip) - 10}")
                remaining_words = [w for w in remaining_words if w not in words_to_skip]
            
            if not remaining_words:
                break
            
            total_chunks = (len(remaining_words) // chunk_size) + (1 if len(remaining_words) % chunk_size else 0)
            
            all_dirty_words = []
            
            with tqdm(total=total_chunks, unit="чанк", desc=f"Раунд {attempt_number}") as pbar:
                for i in range(0, len(remaining_words), chunk_size):
                    chunk = remaining_words[i:i+chunk_size]
                    pbar.set_description(f"Раунд {attempt_number} | Чанк {i//chunk_size + 1}/{total_chunks}")
                    
                    is_retry = attempt_number > 1
                    _, dirty_words = get_transcriptions_via_api(chunk, all_transcriptions, is_retry=is_retry)
                    
                    # Увеличиваем счетчик попыток для всех слов в чанке
                    for word in chunk:
                        retry_counts[word] += 1
                    
                    # Собираем "грязные" слова для следующего раунда
                    all_dirty_words.extend(dirty_words)
                    
                    pbar.update(1)
            
            # Убираем из remaining_words те, что уже в кэше (успешно обработаны)
            remaining_words = [w for w in remaining_words if w not in all_transcriptions]
            
            # Если после раунда ничего не изменилось — выходим, чтобы не зациклиться
            if not remaining_words:
                break
            
            print(f"\n📊 Итог раунда {attempt_number}:")
            print(f"   ✅ Успешно обработано: {len(all_transcriptions)} слов")
            print(f"   🔄 Требуют еще попыток: {len(remaining_words)} слов")
            
            # Небольшая пауза между раундами
            time.sleep(1)

    # 3. Финальная генерация текста с учетом регистра
    print("\n✨ Применяю замены с учетом регистра...")
    
    sorted_words = sorted(all_transcriptions.keys(), key=len, reverse=True)
    new_text = text
    
    for word in tqdm(sorted_words, desc="Замена слов", leave=False):
        if word in new_text:
            transcription = all_transcriptions[word]
            
            def replacer(match):
                original = match.group(0)
                return apply_case(original, transcription)
            
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            new_text = pattern.sub(replacer, new_text)
            
    print(f"💾 Сохраняю итоговый файл: {OUTPUT_FILE}")
    Path(OUTPUT_FILE).write_text(new_text, encoding="utf-8")
    
    if Path(CACHE_FILE).exists():
        Path(CACHE_FILE).unlink()
        print("🧹 Временный кэш удален.")
    
    print(f"\n🎉 Готово! Обработано {len(all_transcriptions)} слов.")
    print(f"Используйте файл {OUTPUT_FILE} для generate_dataset.py")

if __name__ == "__main__":
    print(f"🔌 Подключение к {LLM_API_URL}...")
    try:
        requests.get("http://127.0.0.1:8081/v1/models", timeout=5)
        print("✅ Сервер доступен.\n")
    except Exception:
        print("❌ Не удалось соединиться с портом 8081.\n")
    
    main()