#!/usr/bin/env python3
"""
Создаёт metadata.csv прямо в папке dataset_nikolai.
Формат: полный_путь_к_wav|текст
Логика кавычек: убираем только одиночные, пары оставляем.
"""
import re
from pathlib import Path

DATASET_DIR_NAME = "dataset_nikolai"
OUTPUT_FILE_NAME = "metadata.csv"

def clean_text(text: str) -> str:
    # Базовая очистка
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('…', '.')
    text = text.strip()
    
    if not text:
        return ""

    # Подсчет кавычек
    # Учитываем разные типы кавычек
    double_quotes = ['"', '“', '”']
    single_quotes = ["'", '‘', '’']
    
    count_d = sum(text.count(q) for q in double_quotes)
    count_s = sum(text.count(q) for q in single_quotes)
    
    # Если кавычек НЕ две (не пара), удаляем их все
    if count_d != 2:
        for q in double_quotes:
            text = text.replace(q, '')
            
    if count_s != 2:
        for q in single_quotes:
            text = text.replace(q, '')
    
    return text.strip()

# Пути
script_dir = Path.cwd()
dataset_path = script_dir / DATASET_DIR_NAME
output_csv = dataset_path / OUTPUT_FILE_NAME

if not dataset_path.exists():
    print(f"❌ Ошибка: Папка {dataset_path} не найдена!")
    exit(1)

print(f"📂 Сканирую: {dataset_path}")

valid_count = 0
invalid_count = 0

with open(output_csv, "w", encoding="utf-8") as out:
    for wav_file in sorted(dataset_path.glob("*.wav")):
        lab_file = wav_file.with_suffix(".lab")
        if not lab_file.exists():
            txt_file = wav_file.with_suffix(".txt")
            if txt_file.exists():
                lab_file = txt_file
            else:
                invalid_count += 1
                continue
        
        try:
            raw_text = lab_file.read_text(encoding="utf-8")
            clean_transcript = clean_text(raw_text)
            
            if len(clean_transcript) < 5:
                invalid_count += 1
                continue
            
            out.write(f"{wav_file}|{clean_transcript}\n")
            valid_count += 1
            
        except Exception as e:
            print(f"⚠️ Ошибка {lab_file.name}: {e}")
            invalid_count += 1

print(f"\n✅ Готово: {output_csv}")
print(f"📝 Строк: {valid_count}")
if invalid_count > 0:
    print(f"⚠️ Пропущено: {invalid_count}")

# Показать примеры
print("\nПримеры строк:")
with open(output_csv, "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3: break
        print(line.strip())