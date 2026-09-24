#!/usr/bin/env python3
"""
Генерация текста для TTS с фонетической заменой английских слов.
Работает мгновенно, без LLM, 100% детерминировано.
"""
import re
from pathlib import Path

# === НАСТРОЙКИ ===
INPUT_FILE = "source_text/source_text.txt"
OUTPUT_FILE = "source_text/source_text_for_tts.txt"

# Словарь частых слов, которые стандартная транслитерация портит.
# Добавляй сюда слова по мере необходимости. Формат: "английское": "как читать по-русски"
PHONETIC_DICT = {
    "commit": "коммит", "push": "пуш", "pull": "пулл", "merge": "мерж",
    "feature": "фича", "bug": "баг", "deploy": "деплой", "docker": "докер",
    "kubernetes": "кубернетес", "api": "апи", "json": "джейсон",
    "rejected": "риджектед", "challenges": "чайлдженсиз", "fool": "фуул",
    "medical": "медикал", "approach": "апроуч", "comprehend": "компрехенд",
    "whatever": "ваatever", "changed": "чейнджд", "garage": "гараж",
    "scientists": "сайентистс", "understand": "андерстенд", "here": "хир",
    "forward": "форвард", "almost": "олмоуст", "much": "мач",
    "crucial": "крушал", "sneak": "сник", "expectations": "экспектейшнс",
    "playing": "плеинг", "after": "афтер", "smart": "смарт",
    "expanding": "экспандиг", "intense": "интенс", "hour": "ауэр",
    "curve": "кёрв", "indeed": "индид", "handy": "хэнди",
    "cognition": "когнишн", "says": "сэйз", "contact": "контакт",
    "pictures": "пикчерс", "workshop": "воркшоп", "telescope": "телескоуп",
    "entrance": "энтранс", "cultural": "калчерал", "living": "ливинг",
    "bullets": "буллитс", "still": "стил", "cracked": "крэкт",
    "shape": "шейп", "building": "билдинг", "died": "дайд",
    "space": "спейс", "wants": "вонтс", "plot": "плот",
    "notice": "ноутис", "tone": "тоун", "taking": "тейкинг",
    "family": "фэмили", "network": "нетворк", "server": "сервер",
    "database": "датабейз", "interface": "интерфейс", "user": "юзер",
    "system": "систем", "process": "процесс", "thread": "тред",
    "queue": "кью", "cache": "кэш", "log": "лог", "error": "эррор"
}

def apply_case(original_word: str, target_word: str) -> str:
    """Сохраняет регистр исходного слова."""
    if not original_word: return target_word
    if original_word.isupper(): return target_word.upper()
    elif original_word[0].isupper(): return target_word.capitalize()
    return target_word.lower()

def transliterate_word(word: str) -> str:
    """Простая, но эффективная транслитерация для TTS."""
    # Если слово есть в нашем умном словаре, берем оттуда
    if word.lower() in PHONETIC_DICT:
        return apply_case(word, PHONETIC_DICT[word.lower()])
    
    # Иначе используем простую посимвольную замену (аналог библиотеки transliterate)
    # Эта карта настроена так, чтобы Acapela читала это максимально по-английски
    mapping = {
        'a': 'а', 'b': 'б', 'c': 'к', 'd': 'д', 'e': 'е', 'f': 'ф',
        'g': 'г', 'h': 'х', 'i': 'и', 'j': 'дж', 'k': 'к', 'l': 'л',
        'm': 'м', 'n': 'н', 'o': 'о', 'p': 'п', 'q': 'кв', 'r': 'р',
        's': 'с', 't': 'т', 'u': 'у', 'v': 'в', 'w': 'в', 'x': 'кс',
        'y': 'й', 'z': 'з',
        'sh': 'ш', 'ch': 'ч', 'th': 'з', 'ph': 'ф', 'ee': 'и', 'oo': 'у'
    }
    
    lower_word = word.lower()
    result = lower_word
    
    # Сначала заменяем диграфы (2 буквы)
    for eng, ru in [('sh', 'ш'), ('ch', 'ч'), ('th', 'з'), ('ph', 'ф'), ('ee', 'и'), ('oo', 'у'), ('qu', 'кв')]:
        result = result.replace(eng, ru)
        
    # Потом одиночные буквы
    for eng, ru in mapping.items():
        if len(eng) == 1:
            result = result.replace(eng, ru)
            
    return apply_case(word, result)

def process_text(text: str) -> str:
    """Находит все английские слова и заменяет их."""
    # Находим слова из латинских букв (минимум 2 символа)
    def replacer(match):
        original_word = match.group(0)
        return transliterate_word(original_word)
    
    # \b - граница слова, [a-zA-Z]+ - только латиница
    return re.sub(r'\b[a-zA-Z]+\b', replacer, text)

def main():
    input_path = Path(INPUT_FILE)
    if not input_path.exists():
        print(f"❌ Файл {INPUT_FILE} не найден!")
        return
    
    print(f"📖 Читаю {INPUT_FILE}...")
    text = input_path.read_text(encoding="utf-8")
    
    print("⚡ Обрабатываю текст (это займет 0.1 секунды)...")
    new_text = process_text(text)
    
    output_path = Path(OUTPUT_FILE)
    output_path.write_text(new_text, encoding="utf-8")
    
    print(f"✅ Готово! Файл сохранен: {OUTPUT_FILE}")
    print("💡 Теперь можешь запускать generate_dataset.py")

if __name__ == "__main__":
    main()