# DataCon ChemX: извлечение данных по Benzimidazoles

Репозиторий содержит воспроизводимый пайплайн для финальной задачи DataCon'26
ChemX: извлечение структурированных записей из научных PDF и экспорт в
ChemX-совместимый CSV.

Публичное решение намеренно ограничено одним доменом:
`Benzimidazoles`. Финальный путь детерминированный и rules-only: он не делает
LLM-вызовы и не использует RAG, агентные sidecar-процессы, MolScribe, DECIMER,
YOLO, OCR-стек или распознавание структур по изображениям как часть метрик.

```text
PDF -> парсер -> evidence -> правила -> нормализация -> валидация -> ChemX CSV -> оценка -> Streamlit UI
```

## Итоговый результат

Финальный сохраненный полный запуск:

```text
outputs/benzimidazoles_full/
```

| Метрика | Значение |
|---|---:|
| Домен | Benzimidazoles |
| Режим | rules-only |
| PDF обработано | 31/31 локально доступных |
| Строк предсказаний | 2247 |
| Строк ground truth | 1721 |
| Macro-F1 локального evaluator | 0.4622 |
| Опубликованный single-agent baseline | 0.217 |

Результат выше опубликованного single-agent baseline в локальном evaluator
репозитория. Этот evaluator является приближением benchmark-поведения; parity с
официальным scorer не заявляется.

## Экспериментальный второй домен: Synergy

Помимо стабильного результата `Benzimidazoles`, в репозитории есть
экспериментальный rules-first MVP для `Synergy`:

```text
outputs/synergy_full/
```

На локально доступных PDF для `Synergy` он показал Macro-F1 `0.3626` против
опубликованного single-agent baseline `0.080` в локальном evaluator
репозитория. Финальный экспериментальный запуск выбрал 81 PDF, дал 6647
prediction rows против 3089 local ground-truth rows и не имел failed article
rows. Этот результат отделен от основного claim: `Synergy` имеет более широкую
42-колоночную схему, остается экспериментальным вторым доменом, и parity с
официальным scorer не заявляется.

Воспроизводимая команда:

```powershell
.\.venv\Scripts\python.exe scripts\run_synergy_experimental.py `
  --pdf-dir data\chemx\synergy\pdfs `
  --ground-truth data\chemx\synergy\ground_truth.csv `
  --output-dir outputs\synergy_full
```

## Установка

Создайте локальное окружение репозитория:

```powershell
.\setup_project_env.cmd
```

Если зависимости еще не установлены:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Для проектных команд используйте только интерпретатор репозитория:

```powershell
.\.venv\Scripts\python.exe
```

## Полный rules-only запуск

```powershell
.\.venv\Scripts\python.exe scripts\run_benzimidazoles_full.py `
  --pdf-dir data\chemx\benzimidazoles\pdfs `
  --ground-truth data\chemx\benzimidazoles\ground_truth.csv `
  --output-dir outputs\benzimidazoles_full `
  --llm-mode never
```

Основные файлы результата:

```text
predictions.csv              итоговый ChemX CSV с 7 публичными колонками
review_records.csv/.json     review-only provenance/evidence sidecars
metrics.json                 агрегированные локальные метрики
field_metrics.csv            precision/recall/F1 по полям
article_summary.csv          статус и метрики по PDF
run_manifest.json            параметры запуска и воспроизводимость
```

Публичный `predictions.csv` содержит строго эти колонки:

```text
compound_id,smiles,target_type,target_relation,target_value,target_units,bacteria
```

## Streamlit-интерфейс

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Интерфейс поддерживает три режима:

- просмотр сохраненного полного запуска с метриками, article summary,
  predictions, evidence/review-контекстом и файлами для скачивания;
- запуск одной статьи в rules-only режиме;
- полный запуск датасета после явного подтверждения.

## Ограничения

- Заявленный результат относится только к домену `Benzimidazoles`.
- Финальный запуск rules-only и не делает LLM-вызовов.
- SMILES не решены и экспортируются как `NOT_DETECTED`; поле `smiles` имеет
  F1 `0.0000`.
- Распознавание структур по изображениям не входит в финальные метрики и
  остается будущей работой.
- Recall ограничен, качество заметно различается между PDF.
- Локальный evaluator используется для воспроизводимой проверки, но не
  гарантирует полное совпадение с официальным scorer.

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [RESULTS.md](RESULTS.md)

