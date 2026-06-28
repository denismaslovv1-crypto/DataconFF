# DataCon ChemX: извлечение данных по Benzimidazoles

Репозиторий содержит воспроизводимый пайплайн для финальной задачи DataCon'26
ChemX: извлечение структурированных записей из научных PDF и экспорт в
ChemX-совместимый CSV.

Публичное решение поддерживает два ChemX-домена: Primary domain
`Benzimidazoles` и Additional domain `Synergy`. 

Финальный пайплайн — воспроизводимый **rules-first / rules-only** подход: локальное разбиение PDF, данные извлекаются детерминированными правилами, затем нормализуются, валидируются и оцениваются по схеме ChemX.

LLM, RAG, и другие агентные процессы для распознавания структур по изображениям не используются в финальных метриках.

```text
PDF -> парсер -> evidence -> правила -> нормализация -> валидация -> ChemX CSV -> оценка -> Streamlit UI
```

## Финальные результаты

| Домен          | Роль           | Результаты                    | Macro-F1 | Бейзлайн | Улучшение |
| -------------- | -------------- | ----------------------------- | -------: | -------: | --------: |
| Benzimidazoles | Основной       | `outputs/benzimidazoles_full` | `0.4622` |  `0.217` |  `~2.13x` |
| Synergy        | Дополнительный | `outputs/synergy_full`        | `0.3626` |  `0.080` |  `~4.53x` |

Метрики приведены отдельно для каждого домена. Для воспроизводимого сравнения используется локальный evaluator репозитория.
В колонке «Результаты» указаны папки `outputs/...`, где сохранены результаты запуска: итоговый predictions.csv, агрегированные метрики, метрики по полям и сводка по статьям.

## Primary Domain: Benzimidazoles

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

Результат превышает опубликованный single-agent baseline для Benzimidazoles в локальном evaluator репозитория.

## Additional Domain: Synergy

Помимо стабильного результата `Benzimidazoles`, в репозитории есть
дополнительный rules-first результат для `Synergy`:

```text
outputs/synergy_full/
```

На локально доступных PDF этот запуск показал Macro-F1 0.3626 против опубликованного single-agent baseline 0.080.
Было выбрано 81 PDF, получено 6647 prediction rows против 3089 local ground-truth rows; failed article rows отсутствуют.

Воспроизводимая команда:

```powershell
.\.venv\Scripts\python.exe scripts\run_synergy_experimental.py `
  --pdf-dir data\chemx\synergy\pdfs `
  --ground-truth data\chemx\synergy\ground_truth.csv `
  --output-dir outputs\synergy_full
```

## Установка

Создание локальное окружение репозитория:

```powershell
.\setup_project_env.cmd
```

Если зависимости еще не установлены:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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
- Финальный запуск rules-only и по-умолчанию не делает LLM-вызовов.
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

## Ссылки
[DataCon26](https://github.com/ai-chem/DataCon26/) — постановка задачи
[ChemX](https://github.com/ai-chem/ChemX) — бенчмарк и baseline
[Датасеты ChemX](https://huggingface.co/collections/ai-chem/chemx) (Hugging Face)
