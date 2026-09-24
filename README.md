# Nikolai ML: TTS Training Pipeline

Docker-проект для создания и обучения русскоязычной TTS-модели (голос "Nicolai") на базе **Piper** с использованием GPU.

Особенность проекта — автоматическая подготовка датасета с идеальной фонетической транслитерацией английских слов (IT-терминов) для естественного звучания.

## 🛠 Requirements

*   Docker & Docker Compose
*   NVIDIA GPU + NVIDIA Container Toolkit
*   Python 3.10+ (для скриптов генерации датасета)
*   Wine (для работы Acapela Balabolka в Linux)

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/pelkoa-glitch/nikolai_ml
cd nikolai_ml

# Установка зависимостей для генерации датасета
poetry install --no-root
```

### 2. Prepare Dataset (Генерация аудио и метаданных)

Этот этап создает файлы `.wav` и `metadata.csv`. Скрипт использует голос Acapela Nicolai и библиотеку `g2p_en` для точной транслитерации.

1.  Поместите исходный текст в `source_text/source_text.txt`.
2.  Запустите генератор:

```bash
poetry run python generate_dataset.py
```

*Результат:* Папка `dataset_nikolai/` с аудиофайлами и файлом `metadata.csv`.

### 3. Build & Start Docker

```bash
docker compose build
docker compose up -d
```

### 4. Enter Container

```bash
docker exec -it piper-train-nikolai bash
```

## 📂 Dataset Structure

Проект ожидает датасет в формате LJSpeech внутри контейнера по пути `/nikolai_ml/dataset_nikolai/`:

```text
dataset_nikolai/
├── metadata.csv       # Формат: filename.wav|transcription text
├── nikolai_00000.wav
├── nikolai_00001.wav
└── ...
```

## ⚙️ Preprocessing

Внутри контейнера подготовьте данные к обучению:

```bash
python -m piper_train.preprocess \
    --input-dir /nikolai_ml/dataset_nikolai \
    --output-dir /nikolai_ml/preprocessed \
    --language ru \
    --sample-rate 22050 \
    --dataset-format ljspeech \
    --single-speaker \
    --max-workers 4
```

## 🧠 Training

Запуск обучения на GPU:

```bash
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

python -m piper_train \
    --dataset-dir /nikolai_ml/preprocessed \
    --default_root_dir /nikolai_ml/checkpoints \
    --accelerator gpu \
    --devices 1 \
    --batch-size 8 \
    --validation-split 0.05 \
    --max_epochs 1000 \
    --checkpoint-epochs 50 \
    --hidden-channels 96 \
    --inter-channels 96 \
    --filter-channels 384 \
    --n-layers 4 \
    --n-heads 2
```

> **Note:** Если возникает `CUDA out of memory`, уменьшите `--batch-size`.

## 🧪 Testing & Inference

Проверка качества модели на тестовых фразах:

```bash
head -n 16 /nikolai_ml/preprocessed/dataset.jsonl | python -m piper_train.infer \ 
    --checkpoint /path/to/your/checkpoint.ckpt \ 
    --output-dir /nikolai_ml/output_test \ 
    --sample-rate 22050
```

## 📦 Export to ONNX

Экспорт модели для использования в Piper или других приложениях:

```bash
python -m piper_train.export_onnx \
    /path/to/your/checkpoint.ckpt \
    /nikolai_ml/export/model.onnx
```

## 🛑 Management

*   **Stop:** `docker compose down`
*   **Restart:** `docker compose up -d`
*   **Check GPU:** `nvidia-smi`
*   **Clean Logs:** `rm -rf checkpoints/lightning_logs`

---
*Created with ❤️ for high-quality Russian TTS.*
```