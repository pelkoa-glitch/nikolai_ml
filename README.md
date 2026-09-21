# TTS Training

Docker-проект для обучения TTS-моделей на GPU.

## Requirements

* Docker
* Docker Compose
* NVIDIA GPU + NVIDIA Container Toolkit (для NVIDIA)
* Датасет в поддерживаемом формате

## Quick Start

### 1. Clone

```bash
git clone https://github.com/pelkoa-glitch/nikolai_ml
cd nikolai_ml
```

### 2. Build

```bash
docker compose build
```

### 3. Start

```bash
docker compose up -d
```

### 4. Enter container

```bash
docker exec -it piper-train-nikolai bash
```

## Dataset

Поместите исходный датасет в директорию проекта:

```text
dataset/
├── metadata.csv
├── audiofile_0.wav
├── audiofile_1.wav
└── audiofile_n.wav
```

Подготовьте датасет:

```bash
python -m piper_train.preprocess \
    --input-dir <input-dir> \
    --output-dir <output-dir> \
    --language <language> \
    --sample-rate <sample-rate> \
    --dataset-format ljspeech \
    --single-speaker
```

## Training

Запустите обучение:

```bash
python -m piper_train \
    --dataset-dir <preprocessed-dir> \
    --default_root_dir <checkpoints-dir> \
    --accelerator gpu \
    --devices 1 \
    --batch-size <batch-size> \
    --max_epochs <max-epochs> \
    --checkpoint-epochs <checkpoint-interval> \
    --resume_from_checkpoint <path-to-checkpoint>
```

`batch-size` зависит от доступной VRAM.
Если появляется `CUDA out of memory`, уменьшите его.

## Checkpoints

Checkpoints сохраняются в указанной директории и позволяют продолжить обучение после остановки.

Не удаляйте их во время обучения.

## Тестироание
### Команда для генерации wav на выбранном чекпоинте
```
head -n 16 /nikolai_ml/preprocessed/dataset.jsonl | python -m piper_train.infer \ 
    --checkpoint /nikolai_ml/checkpoints/lightning_logs/version_2/checkpoints/epoch=99-step=90600.ckpt \ 
    --output-dir /nikolai_ml/output_test \ 
    --sample-rate 22050
```

## Экспорт модели
```
python -m piper_train.export_onnx \
    <path-to-checkpoint> \
    <destination-folder>/<model-name>.onnx
```

## Stop

```bash
docker compose down
```

Для повторного запуска:

```bash
docker compose up -d
```

## GPU

Для NVIDIA можно проверить доступность GPU:

```bash
nvidia-smi
```

Готово — после запуска команды `piper_train` начнётся обучение.

## Примеры команд

Start container:
```
docker compose up --build -d
```

Open a bash console in the container.:
```
docker exec -it piper-train-nikolai bash
```

Preprocess script:
```
python -m piper_train.preprocess \
    --input-dir /nikolai_ml/dataset_nikolai \
    --output-dir /nikolai_ml/preprocessed \
    --language ru \
    --sample-rate 22050 \
    --dataset-format ljspeech \
    --single-speaker \
    --max-workers 4
```

Start script:
```
cd /nikolai_ml

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
    --n-heads 2 \
    --resume_from_checkpoint /nikolai_ml/checkpoints/lightning_logs/version_0/checkpoints/epoch=49-step=45300.ckpt
```

Delete logs and checkpoints
```
rm -rf checkpoints/lightning_logs
```
