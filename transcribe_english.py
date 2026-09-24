#!/usr/bin/env python3
"""
Скрипт для транскрибации английских слов через llama.cpp API.
Функции:
- Потоковая запись в кэш (устойчивость к сбоям).
- Сохранение регистра букв (Commit -> Коммит, COMMIT -> КОММИТ).
- Вывод отправляемых слов в консоль.
- Увеличенный таймаут (10 мин).
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
CACHE_FILE = "transcriptions_cache.json"  # Промежуточный файл

LLM_API_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf" 

# ТАЙМАУТ: 10 минут (600 секунд)
REQUEST_TIMEOUT = 600 

def apply_case(original_word: str, target_word: str) -> str:
    """
    Применяет регистр original_word к target_word.
    Примеры:
    'Hello' + 'привет' -> 'Привет'
    'HELLO' + 'привет' -> 'ПРИВЕТ'
    'hello' + 'привет' -> 'привет'
    """
    if not original_word:
        return target_word
    
    if original_word.isupper():
        return target_word.upper()
    elif original_word[0].isupper():
        return target_word.capitalize()
    else:
        return target_word.lower()

def extract_unique_english_words(text):
    """Извлекает все уникальные слова, состоящие только из латиницы (минимум 2 буквы)."""
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    return list(set(words))

def load_existing_cache():
    """Загружает уже обработанные слова из кэша."""
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
    """Сохраняет текущий словарь транскрипций в файл."""
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(transcriptions, f, ensure_ascii=False, indent=2)

def get_transcriptions_via_api(words, all_cache):
    if not words:
        return {}
    
    words_to_process = [w for w in words if w not in all_cache]
    if not words_to_process:
        return {}

    words_preview = ", ".join(words_to_process)
    print(f"\n📤 Отправляем ({len(words_to_process)} слов): {words_preview}")
    
    words_list_str = ", ".join([f'"{w}"' for w in words_to_process])
    
    # Промпт максимально короткий, чтобы сэкономить токены на размышления
    system_prompt = (
        "You are a strict phonetic transcriber. "
        "Task: Convert English words to Russian Cyrillic phonetics. "
        "STRICT RULES:\n"
        "1. Output ONLY raw JSON. No thinking, no reasoning, no markdown.\n"
        "2. Values MUST contain ONLY Cyrillic letters (А-Я, а-я). \n"
        "3. NEVER mix Latin and Cyrillic in the same word.\n"
        "4. BAD example: 'approach' -> 'апroach' (Contains Latin!), 'infrastructure' -> 'инфрастракчер' (NOT 'инфраструктура').\n"
        "5. GOOD example: 'approach' -> 'апроуч' (Only Cyrillic!)\n"
        "6. Do not translate meanings, transcribe sounds."
    )
    
    user_prompt = (
        "Transcribe these words to Russian phonetics (strictly Cyrillic only)"
        "Example: {\"commit\":\"коммит\",\"push\":\"пуш\",\"feature\":\"фича\"}\n"
        "Now transcribe: " + words_list_str
    )

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False
    }

    try:
        start_time = time.time()
        response = requests.post(LLM_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
        duration = time.time() - start_time
        
        print(f"⏱️ Время ожидания ответа: {duration:.1f}с | Статус HTTP: {response.status_code}")

        if response.status_code != 200:
            print(f"❌ Ошибка сервера! Ответ:\n{response.text[:500]}")
            return {}
            
        try:
            api_response = response.json()
        except ValueError:
            print(f"❌ Сервер вернул не JSON! Ответ:\n{response.text[:500]}")
            return {}

        # === ПОЛНАЯ ОТЛАДКА: Выводим всё, что пришло ===
        print("-" * 40)
        print(" ДИАГНОСТИКА ОТВЕТА МОДЕЛИ:")
        
        if "choices" in api_response and len(api_response["choices"]) > 0:
            choice = api_response["choices"][0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "unknown")
            
            content = message.get("content", "")
            reasoning = message.get("reasoning_content", "")
            
            print(f"   Finish Reason: {finish_reason}")
            print(f"   Длина Content: {len(content)} симв.")
            print(f"   Длина Reasoning: {len(reasoning)} симв.")
            
            # Если контент пустой, покажем, что было в reasoning (часто проблема там)
            if not content.strip():
                print("   ⚠️ CONTENT ПУСТОЙ! Вот что модель 'думала' (Reasoning):")
                print(f"   >>> {reasoning}...") # Первые 300 символов
            else:
                print(f"   ✅ Content (первые 200 симв): {content}")
        else:
            print("   ❌ В ответе нет блока 'choices'. Полный ответ:")
            print(f"   {api_response}")
            
        print("-" * 40)

        # === ЛОГИКА ИЗВЛЕЧЕНИЯ ===
        if "choices" not in api_response or len(api_response["choices"]) == 0:
            return {}

        choice = api_response["choices"][0]
        message = choice.get("message", {})
        raw_text = message.get("content", "")

        if not raw_text or not raw_text.strip():
            print(" Итог: Модель не сгенерировала полезный контент (пусто).")
            return {}

        # Попытка найти JSON
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            print(f"❌ JSON не найден в тексте. Текст:\n{raw_text[:200]}")
            return {}
        
        json_str = raw_text[start_idx : end_idx + 1]
        
        try:
            new_transcriptions = json.loads(json_str)
            if isinstance(new_transcriptions, dict):
                all_cache.update(new_transcriptions)
                save_to_cache(all_cache)
                print(f"✅ УСПЕХ! Получено {len(new_transcriptions)} слов за {duration:.1f}с.")
                return new_transcriptions
            else:
                print(f"❌ Парсинг успешен, но это не словарь (тип: {type(new_transcriptions)}).")
                return {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"   Фрагмент для проверки:\n{json_str[:200]}")
            return {}
        
    except requests.exceptions.Timeout:
        print(f"\n⏳ ТАЙМАУТ ({REQUEST_TIMEOUT}с). Модель думает слишком долго.")
        return {}
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {}

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

    # 1. Загружаем已有的 кэш
    all_transcriptions = load_existing_cache()
    
    # Исключаем уже обработанные слова из списка задач
    remaining_words = [w for w in unique_words if w not in all_transcriptions]
    
    if not remaining_words:
        print("🎉 Все слова уже обработаны! Перехожу к созданию файла...")
    else:
        print(f"🚀 Осталось обработать: {len(remaining_words)} слов.")
        
        chunk_size = 50  # Маленький чанк для надежности при больших моделях
        total_chunks = (len(remaining_words) // chunk_size) + (1 if len(remaining_words) % chunk_size else 0)
        
        with tqdm(total=total_chunks, unit="чанк", desc="Транскрибация") as pbar:
            for i in range(0, len(remaining_words), chunk_size):
                chunk = remaining_words[i:i+chunk_size]
                pbar.set_description(f"Чанк {i//chunk_size + 1}/{total_chunks}")
                
                get_transcriptions_via_api(chunk, all_transcriptions)
                pbar.update(1)

    # 2. Финальная генерация текста с учетом регистра
    print("\n✨ Применяю замены с учетом регистра...")
    
    # Сортируем от длинных к коротким, чтобы заменить "installation" до "install"
    sorted_words = sorted(all_transcriptions.keys(), key=len, reverse=True)
    new_text = text
    
    for word in tqdm(sorted_words, desc="Замена слов", leave=False):
        if word in new_text:
            transcription = all_transcriptions[word]
            
            def replacer(match):
                original = match.group(0)
                return apply_case(original, transcription)
            
            # \b гарантирует замену целого слова, re.IGNORECASE учитывает регистр
            pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
            new_text = pattern.sub(replacer, new_text)
            
    print(f"💾 Сохраняю итоговый файл: {OUTPUT_FILE}")
    Path(OUTPUT_FILE).write_text(new_text, encoding="utf-8")
    
    # Опционально: удаляем временный кэш после успешного завершения
    if Path(CACHE_FILE).exists():
        Path(CACHE_FILE).unlink()
        print("🧹 Временный кэш удален.")
    
    print(f"\n Готово! Обработано {len(all_transcriptions)} слов.")
    print(f"Используйте файл {OUTPUT_FILE} для generate_dataset.py")

if __name__ == "__main__":
    print(f" Проверка подключения к {LLM_API_URL}...")
    try:
        # Быстрая проверка доступности API
        requests.get("http://127.0.0.1:8080/v1/models", timeout=5)
        print("✅ Сервер доступен.\n")
    except Exception:
        print("❌ Не удалось соединиться с портом 8080. Убедись, что llama.cpp запущен!\n")
        # Не выходим сразу, даем шанс ошибке проявиться позже
    
    main()