#!/usr/bin/env python3
"""
Генерация датасета для Piper через Balabolka Console (Wine, SAPI4).
Голос: Acapela Elan TTS Nicolai
ТЕПЕРЬ ПОДДЕРЖИВАЕТ ПАРУ ФАЙЛОВ: оригинал для .lab и фонетику для .wav
"""
import os
import re
import subprocess
import sys
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path

# === НАСТРОЙКИ ===
BALCON_PATH = os.path.expanduser("~/.wine/drive_c/Program Files (x86)/Balabolka/balcon.exe")
VOICE_NAME = "Nicolai"
DICT_PATH = os.path.expanduser("~/.wine/drive_c/Program Files (x86)/Balabolka/michelangelo.dic")

# ВАЖНО: Указываем ОБА файла
INPUT_TEXT_PHONETIC = "source_text/source_text_for_tts.txt" # Для озвучки
INPUT_TEXT_ORIGINAL = "source_text/source_text.txt"         # Для меток (.lab)

OUTPUT_DIR = "dataset_nikolai"
MIN_SENTENCE_LEN = 15
MAX_SENTENCE_LEN = 250

# === ИНИЦИАЛИЗАЦИЯ ===
Path(OUTPUT_DIR).mkdir(exist_ok=True)

def parse_args():
    parser = argparse.ArgumentParser(description="Генерация датасета для Piper")
    parser.add_argument("--max-phrases", type=int, default=None, help="Максимум фраз")
    parser.add_argument("--start-index", type=int, default=0, help="Начальный индекс нумерации")
    return parser.parse_args()

def check_dependencies():
    if subprocess.run(["which", "wine"], capture_output=True).returncode != 0:
        sys.exit("❌ Не найден wine. Установи: sudo pacman -S wine")
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        sys.exit("❌ Не найден ffmpeg. Установи: sudo pacman -S ffmpeg")
    if not os.path.exists(BALCON_PATH):
        sys.exit(f"❌ Не найден balcon.exe: {BALCON_PATH}")
    print("✅ Зависимости найдены.")

def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('…', '.')
    text = re.sub(r'https?://\S+', '', text)
    return text.strip()

def split_into_sentences(text):
    text = clean_text(text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    result = []
    
    for s in sentences:
        s = s.strip()
        if not s:
            continue
            
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

def generate_wav(text: str, wav_path: Path) -> bool:
    txt_path = wav_path.with_suffix(".tmp.txt")
    txt_path.write_text(text, encoding="utf-8")
    
    try:
        cmd = [
            "wine", BALCON_PATH,
            "-f", str(txt_path),
            "-w", str(wav_path),
            "-n", VOICE_NAME,
            "-fr", "22", "-bt", "16", "-ch", "1",
            "--encoding", "utf8"
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
        if txt_path.exists():
            txt_path.unlink()

def normalize_wav(wav_path: Path):
    temp_path = wav_path.with_suffix(".norm.wav")
    cmd = [
        "ffmpeg", "-y", "-i", str(wav_path),
        "-ar", "22050", "-ac", "1", "-c:a", "pcm_s16le",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        str(temp_path)
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True)
        if temp_path.exists() and temp_path.stat().st_size > 1000:
            temp_path.replace(wav_path)
        elif temp_path.exists():
            temp_path.unlink()
    except Exception:
        if temp_path.exists():
            temp_path.unlink()

def main():
    args = parse_args()
    max_phrases = args.max_phrases
    start_index = args.start_index
    
    print(f"🚀 Начало генерации: {datetime.now().strftime('%H:%M:%S')}")
    check_dependencies()
    
    # 1. Читаем ОБА файла
    if not Path(INPUT_TEXT_PHONETIC).exists() or not Path(INPUT_TEXT_ORIGINAL).exists():
        sys.exit("❌ Не найдены файлы source_text.txt или source_text_for_tts.txt")
    
    text_phonetic = Path(INPUT_TEXT_PHONETIC).read_text(encoding="utf-8")
    text_original = Path(INPUT_TEXT_ORIGINAL).read_text(encoding="utf-8")
    
    # 2. Разбиваем ОДНОЙ и той же функцией, чтобы сохранить синхронизацию
    sentences_phonetic = split_into_sentences(text_phonetic)
    sentences_original = split_into_sentences(text_original)
    
    if len(sentences_phonetic) != len(sentences_original):
        print(f"⚠️ ВНИМАНИЕ: Количество фраз не совпадает! (Фонетика: {len(sentences_phonetic)}, Оригинал: {len(sentences_original)})")
        print("   Это может произойти, если длина транслитерации изменила границы MAX_SENTENCE_LEN.")
        print("   Скрипт продолжит работу, сопоставляя файлы по порядку (zip).")
    
    # Берем минимум из двух, чтобы избежать выхода за границы
    total_phrases = min(len(sentences_phonetic), len(sentences_original))
    
    if max_phrases is not None:
        total_phrases = min(total_phrases, max_phrases)
        print(f"🧪 ТЕСТОВЫЙ РЕЖИМ: генерируем только {total_phrases} фраз")
    
    print(f"📝 Найдено {total_phrases} пар фраз для озвучки.")
    
    start_time = time.time()
    success_count = 0
    phrase_times = []
    
    # 3. Итерируемся по ПАРАМ (фонетика для звука, оригинал для текста)
    for i in range(total_phrases):
        phrase_start = time.time()
        global_index = i + start_index
        
        phonetic_sentence = sentences_phonetic[i]
        original_sentence = sentences_original[i]
        
        wav_name = f"nikolai_{global_index:05d}.wav"
        lab_name = f"nikolai_{global_index:05d}.lab"
        wav_path = Path(OUTPUT_DIR) / wav_name
        lab_path = Path(OUTPUT_DIR) / lab_name
        
        if wav_path.exists() and lab_path.exists():
            success_count += 1
            continue
        
        elapsed = time.time() - start_time
        elapsed_str = str(timedelta(seconds=int(elapsed)))
        
        if phrase_times:
            avg_time = sum(phrase_times) / len(phrase_times)
            eta_str = str(timedelta(seconds=int(avg_time * (total_phrases - i))))
        else:
            eta_str = "расчёт..."
        
        progress = (i + 1) / total_phrases * 100
        print(f"\r[{progress:5.1f}%] [{i+1}/{total_phrases}] {wav_name} | ⏱️ {elapsed_str} | ETA: {eta_str}", end="", flush=True)
        
        # ВАЖНО: Озвучиваем фонетику, но в .lab пишем оригинал!
        if generate_wav(phonetic_sentence, wav_path):
            normalize_wav(wav_path)
            lab_path.write_text(original_sentence, encoding="utf-8") # <-- ВОТ ГЛАВНОЕ ИЗМЕНЕНИЕ
            success_count += 1
            phrase_times.append(time.time() - phrase_start)
        else:
            if wav_path.exists():
                wav_path.unlink()
    
    total_time_str = str(timedelta(seconds=int(time.time() - start_time)))
    print(f"\n\n🎉 Готово!")
    print(f"✅ Успешно: {success_count}/{total_phrases}")
    if success_count > 0:
        total_size = sum(f.stat().st_size for f in Path(OUTPUT_DIR).glob('*.wav'))
        print(f"📊 Размер датасета: {total_size / 1024 / 1024:.1f} MB")
    print(f"⏱️  Всего затрачено: {total_time_str}")

if __name__ == "__main__":
    main()