#!/usr/bin/env python3
"""
Скрипт для транскрибации английских слов через llama.cpp API.
Версия с визуальным прогрессом (tqdm).
"""
import re
import json
import sys
import time
import requests
from pathlib import Path
from tqdm import tqdm  # Импорт прогресс-бара

# === НАСТРОЙКИ ===
INPUT_FILE = "source_text/source_text.txt"
OUTPUT_FILE = "source_text/source_text_for_tts.txt"

# ИСПРАВЛЕННЫЙ ПОРТ (8080 вместо 8000)
LLM_API_URL = "http://127.0.0.1:8080/v1/chat/completions"
LLM_MODEL = "/models/Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf" # Или имя твоей модели

def extract_unique_english_words(text):
    words = re.findall(r'\b[a-zA-Z]{2,}\b', text)
    return list(set(words))

def get_transcriptions_via_api(words, pbar=None):
    if not words:
        return {}
    
    words_list_str = ", ".join([f'"{w}"' for w in words])
    
    system_prompt = (
        "You are a phonetic transcription expert. "
        "Return ONLY a valid JSON object where keys are original English words "
        "and values are Russian phonetic transcriptions (Cyrillic). "
        "NO markdown, NO explanations, JUST raw JSON."
    )
    
    user_prompt = f"List of words: [{words_list_str}]"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
        "stream": False
    }

    try:
        start_time = time.time()
        response = requests.post(LLM_API_URL, json=payload, timeout=180)
        duration = time.time() - start_time
        
        # ВАЖНО: Проверяем статус код перед парсингом
        if response.status_code != 200:
            msg = f"\n❌ Ошибка сервера ({response.status_code}): {response.text[:200]}"
            if pbar: pbar.write(msg)
            else: print(msg)
            return {}
            
        raw_text = response.text.strip()
        
        # Если ответ пустой
        if not raw_text:
            msg = "\n❌ Пустой ответ от сервера."
            if pbar: pbar.write(msg)
            else: print(msg)
            return {}

        # Попытка найти JSON внутри ответа (на случай, если модель добавила текст)
        # Ищем первую '{' и последнюю '}'
        start_idx = raw_text.find('{')
        end_idx = raw_text.rfind('}')
        
        if start_idx == -1 or end_idx == -1 or start_idx > end_idx:
            # JSON не найден вообще
            msg = f"\n❌ JSON не найден в ответе. Сырой ответ:\n{raw_text[:300]}"
            if pbar: pbar.write(msg)
            else: print(msg)
            return {}
        
        # Вырезаем только JSON часть
        json_str = raw_text[start_idx : end_idx + 1]
        
        try:
            transcriptions = json.loads(json_str)
            if pbar:
                pbar.set_postfix_str(f"⏱️ {duration:.1f}s | ✅ {len(transcriptions)} слов")
            return transcriptions
        except json.JSONDecodeError as e:
            # Если даже вырезанная часть не валидна
            msg = f"\n❌ Ошибка парсинга вырезанного JSON: {e}\nВырезанный фрагмент:\n{json_str[:200]}"
            if pbar: pbar.write(msg)
            else: print(msg)
            return {}
        
    except requests.exceptions.ConnectionError:
        msg = "\n❌ Нет соединения с сервером."
        if pbar: pbar.write(msg)
        else: print(msg)
        return {}
    except Exception as e:
        msg = f"\n❌ Неожиданная ошибка: {e}"
        if pbar: pbar.write(msg)
        else: print(msg)
        return {}

def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f" Файл {INPUT_FILE} не найден!")
        sys.exit(1)
    
    print(f"📖 Читаю {INPUT_FILE}...")
    text = input_path.read_text(encoding="utf-8")
    
    unique_words = extract_unique_english_words(text)
    total_words = len(unique_words)
    print(f" Найдено уникальных слов: {total_words}")
    
    if not unique_words:
        print("️ Английских слов нет. Копирую файл.")
        import shutil
        shutil.copyfile(input_path, OUTPUT_FILE)
        return

    chunk_size = 15
    all_transcriptions = {}
    total_chunks = (total_words // chunk_size) + (1 if total_words % chunk_size else 0)
    
    print("🚀 Начинаю обработку...\n")
    
    # Создаем красивый прогресс-бар
    with tqdm(total=total_chunks, unit="чанк", desc="Транскрибация") as pbar:
        for i in range(0, total_words, chunk_size):
            chunk = unique_words[i:i+chunk_size]
            
            # Описание текущего чанка
            pbar.set_description(f"Чанк {i//chunk_size + 1}/{total_chunks}")
            
            chunk_dict = get_transcriptions_via_api(chunk, pbar=pbar)
            
            if chunk_dict:
                all_transcriptions.update(chunk_dict)
            
            # Обновляем бар (увеличиваем счетчик на 1)
            pbar.update(1)
            
            # Небольшая пауза, чтобы не спамить сервер (опционально)
            # time.sleep(0.1) 

    if not all_transcriptions:
        print("\n❌ Не удалось получить ни одной транскрипции.")
        sys.exit(1)

    # Применяем замены
    print("\n✨ Применяю замены к тексту...")
    sorted_words = sorted(all_transcriptions.keys(), key=len, reverse=True)
    new_text = text
    count = 0
    
    # Прогресс-бар для замены (быстро, но приятно)
    for word in tqdm(sorted_words, desc="Замена слов", leave=False):
        if word in new_text:
            new_text = new_text.replace(word, all_transcriptions[word])
            count += 1
            
    print(f"\n💾 Сохраняю результат в {OUTPUT_FILE}...")
    Path(OUTPUT_FILE).write_text(new_text, encoding="utf-8")
    
    print(f"\n🎉 Готово! Обработано {count} замен.")
    print(f"Файл готов для generate_dataset.py")

if __name__ == "__main__":
    print(f"🔌 Подключение к {LLM_API_URL}...")
    # Быстрая проверка порта
    try:
        requests.get("http://127.0.0.1:8080/v1/models", timeout=2)
        print("✅ Сервер доступен.\n")
    except:
        print("❌ Не удалось соединиться с портом 8080. Запусти сервер!\n")
        # Не выходим сразу, даем шанс скрипту показать ошибку позже в процессе
    
    main()