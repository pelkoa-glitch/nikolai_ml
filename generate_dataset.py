#!/usr/bin/env python3
"""
Генерация датасета для Piper.
Использует g2p_en для идеальной транслитерации английских слов в кириллицу.
"""
import os
import re
import subprocess
import sys
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from g2p_en import G2p

# === НАСТРОЙКИ ===
# Пути адаптированы под структуру nikolai_ml
BALCON_PATH = os.path.expanduser("~/.wine/drive_c/Program Files (x86)/Balabolka/balcon.exe")
VOICE_NAME = "Nicolai"
DICT_PATH = os.path.expanduser("~/.wine/drive_c/Program Files (x86)/Balabolka/michelangelo.dic")

INPUT_TEXT_ORIGINAL = "source_text/en_source.txt" # Относительный путь от корня проекта
OUTPUT_DIR = "dataset_nikolai"
METADATA_FILE = "metadata.csv"

MIN_SENTENCE_LEN = 15
MAX_SENTENCE_LEN = 250

# === ИНИЦИАЛИЗАЦИЯ ===
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

# Инициализируем g2p только если он доступен
try:
    g2p = G2p()
except Exception as e:
    print(f"⚠️ Ошибка загрузки g2p_en: {e}")
    print("Убедись, что установлены зависимости: pip install g2p-en nltk")
    sys.exit(1)

# Маппинг ARPAbet (формат g2p_en) в русскую кириллицу
ARPABET_TO_CYRILLIC = {
    'AA': 'а', 'AA0': 'а', 'AA1': 'а', 'AA2': 'а',
    'AE': 'э', 'AE0': 'э', 'AE1': 'э', 'AE2': 'э',
    'AH': 'а', 'AH0': 'а', 'AH1': 'а', 'AH2': 'а',
    'AO': 'о', 'AO0': 'о', 'AO1': 'о', 'AO2': 'о',
    'AW': 'ау', 'AW0': 'ау', 'AW1': 'ау', 'AW2': 'ау',
    'AY': 'ай', 'AY0': 'ай', 'AY1': 'ай', 'AY2': 'ай',
    'B': 'б', 'CH': 'ч', 'D': 'д', 'DH': 'з',
    'EH': 'э', 'EH0': 'э', 'EH1': 'э', 'EH2': 'э',
    'ER': 'эр', 'ER0': 'эр', 'ER1': 'эр', 'ER2': 'эр',
    'EY': 'эй', 'EY0': 'эй', 'EY1': 'эй', 'EY2': 'эй',
    'F': 'ф', 'G': 'г', 'HH': 'х',
    'IH': 'и', 'IH0': 'и', 'IH1': 'и', 'IH2': 'и',
    'IY': 'и', 'IY0': 'и', 'IY1': 'и', 'IY2': 'и',
    'JH': 'дж', 'K': 'к', 'L': 'л', 'M': 'м', 'N': 'н',
    'NG': 'нг',
    'OW': 'оу', 'OW0': 'оу', 'OW1': 'оу', 'OW2': 'оу',
    'OY': 'ой', 'OY0': 'ой', 'OY1': 'ой', 'OY2': 'ой',
    'P': 'п', 'R': 'р', 'S': 'с', 'SH': 'ш', 'T': 'т', 'TH': 'т',
    'UH': 'у', 'UH0': 'у', 'UH1': 'у', 'UH2': 'у',
    'UW': 'у', 'UW0': 'у', 'UW1': 'у', 'UW2': 'у',
    'V': 'в', 'W': 'у', 'Y': 'й', 'Z': 'з', 'ZH': 'ж'
}

def parse_args():
    parser = argparse.ArgumentParser(description="Генерация датасета")
    parser.add_argument("--max-phrases", type=int, default=None, help="Максимум фраз")
    parser.add_argument("--start-index", type=int, default=0, help="Начальный индекс")
    return parser.parse_args()

def check_dependencies():
    if subprocess.run(["which", "wine"], capture_output=True).returncode != 0:
        sys.exit("❌ Не найден wine.")
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        sys.exit("❌ Не найден ffmpeg.")
    if not os.path.exists(BALCON_PATH):
        sys.exit(f"❌ Не найден balcon.exe: {BALCON_PATH}")
    print("✅ Зависимости найдены.")

def clean_text(text):
    # Базовая очистка
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('…', '.')
    text = re.sub(r'https?://\S+', '', text)
    
    # === ДОБАВЛЕННАЯ ЛОГИКА ДЛЯ КАВЫЧЕК ===
    # Удаляем двойные кавычки (все виды)
    text = text.replace('"', '').replace('“', '').replace('”', '')
    # Удаляем одинарные кавычки/апострофы (все виды)
    text = text.replace("'", '').replace('‘', '').replace('’', '')
    
    return text.strip()

def split_into_sentences(text):
    text = clean_text(text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    for s in sentences:
        s = s.strip()
        if not s: continue
        if MIN_SENTENCE_LEN <= len(s) <= MAX_SENTENCE_LEN:
            result.append(s)
        elif len(s) > MAX_SENTENCE_LEN:
            parts = re.split(r'(?<=[,;:])\s+', s)
            chunk = ""
            for p in parts:
                if len(chunk) + len(p) + 1 < MAX_SENTENCE_LEN:
                    chunk = (chunk + " " + p).strip()
                else:
                    if chunk and len(chunk) >= MIN_SENTENCE_LEN:
                        result.append(chunk)
                    chunk = p
            if chunk and len(chunk) >= MIN_SENTENCE_LEN:
                result.append(chunk)
    return result

def transliterate_english_word(word: str) -> str:
    """Транслитерирует английское слово через g2p_en (ARPAbet -> Кириллица)"""
    if not word or not word.isalpha():
        return word
    
    try:
        phonemes = g2p(word.lower())
    except Exception:
        return word # Фоллбэк если ошибка
    
    result = []
    for ph in phonemes:
        ph_base = re.sub(r'\d', '', ph)
        if ph in ARPABET_TO_CYRILLIC:
            result.append(ARPABET_TO_CYRILLIC[ph])
        elif ph_base in ARPABET_TO_CYRILLIC:
            result.append(ARPABET_TO_CYRILLIC[ph_base])
        else:
            result.append(ph.lower())
            
    cyrillic_word = "".join(result)
    
    if word.isupper():
        return cyrillic_word.upper()
    elif word[0].isupper():
        return cyrillic_word.capitalize()
    return cyrillic_word

def transliterate_sentence(sentence: str) -> str:
    def replacer(match):
        return transliterate_english_word(match.group(0))
    return re.sub(r'\b[a-zA-Z]+\b', replacer, sentence)

def generate_wav(text: str, wav_path: Path) -> bool:
    txt_path = wav_path.with_suffix(".tmp.txt")
    txt_path.write_text(text, encoding="utf-8")
    try:
        cmd = [
            "wine", BALCON_PATH, "-f", str(txt_path), "-w", str(wav_path), 
            "-n", VOICE_NAME, "-fr", "22", "-bt", "16", "-ch", "1", "--encoding", "utf8"
        ]
        if os.path.exists(DICT_PATH):
            cmd.extend(["-d", DICT_PATH])
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env={**os.environ, "WINEDEBUG": "-all"})
        if result.returncode != 0 or not wav_path.exists() or wav_path.stat().st_size < 1000:
            return False
        return True
    except subprocess.TimeoutExpired:
        return False
    finally:
        if txt_path.exists(): txt_path.unlink()

def normalize_wav(wav_path: Path):
    temp_path = wav_path.with_suffix(".norm.wav")
    cmd = [
        "ffmpeg", 
        "-y", 
        "-i", 
        str(wav_path), 
        "-ar", 
        "22050", 
        "-ac", 
        "1", 
        "-c:a", 
        "pcm_s16le", 
        "-af", 
        "loudnorm=I=-23:TP=-3.0:LRA=7",
        str(temp_path)
        ]
    
    try:
        subprocess.run(cmd, capture_output=True, text=True)
        if temp_path.exists() and temp_path.stat().st_size > 1000:
            temp_path.replace(wav_path)
        elif temp_path.exists():
            temp_path.unlink()
    except Exception:
        if temp_path.exists(): temp_path.unlink()

def main():
    args = parse_args()
    print(f"🚀 Начало: {datetime.now().strftime('%H:%M:%S')}")
    check_dependencies()
    
    if not Path(INPUT_TEXT_ORIGINAL).exists():
        sys.exit(f"❌ Не найден файл {INPUT_TEXT_ORIGINAL}. Проверь путь!")
    
    text_original = Path(INPUT_TEXT_ORIGINAL).read_text(encoding="utf-8")
    sentences_original = split_into_sentences(text_original)
    total_phrases = len(sentences_original)
    
    if args.max_phrases:
        total_phrases = min(total_phrases, args.max_phrases)
        print(f"🧪 ТЕСТ: только {total_phrases} фраз")
    
    print(f"📝 Найдено {total_phrases} фраз.")
    
    metadata_path = Path(OUTPUT_DIR) / METADATA_FILE
    processed_wavs = set()
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    processed_wavs.add(line.split("|")[0].strip())
        print(f"📂 Найдено {len(processed_wavs)} готовых файлов. Продолжаем.")
    
    start_time = time.time()
    success_count = len(processed_wavs)
    phrase_times = []
    
    for i in range(total_phrases):
        phrase_start = time.time() # Запоминаем время начала обработки этой фразы
        global_index = i + args.start_index
        original_sentence = sentences_original[i]
        wav_name = f"nikolai_{global_index:05d}.wav"
        wav_path = Path(OUTPUT_DIR) / wav_name
        
        if wav_name in processed_wavs:
            continue
        
        elapsed = time.time() - start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        
        # Расчет ETA
        if phrase_times:
            avg_time = sum(phrase_times) / len(phrase_times)
            remaining = total_phrases - i
            eta_str = str(timedelta(seconds=int(avg_time * remaining)))
        else:
            eta_str = "расчёт..."
            
        progress = (i + 1) / total_phrases * 100
        print(f"\r[{progress:5.1f}%] [{i+1}/{total_phrases}] {wav_name} | ⏱️ {elapsed_str} | ETA: {eta_str}", end="", flush=True)
        
        phonetic_sentence = transliterate_sentence(original_sentence)
        
        if generate_wav(phonetic_sentence, wav_path):
            normalize_wav(wav_path)
            with open(metadata_path, "a", encoding="utf-8") as meta_out:
                meta_out.write(f"{wav_name}|{original_sentence}\n")
            processed_wavs.add(wav_name)
            success_count += 1
            
            # ✅ ИСПРАВЛЕНИЕ: правильно считаем время выполнения фразы
            phrase_duration = time.time() - phrase_start
            phrase_times.append(phrase_duration)
        else:
            if wav_path.exists(): wav_path.unlink()
    
    print(f"\n\n🎉 Готово! Обработано: {success_count}/{total_phrases}")
    print(f"📄 Метаданные: {metadata_path.resolve()}")

if __name__ == "__main__":
    main()