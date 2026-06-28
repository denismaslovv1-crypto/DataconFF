# Архитектура

Публичная отправка использует детерминированный rules-only пайплайн для домена
`Benzimidazoles`.

```text
scientific PDF
  -> локальный PDF parser
  -> text/table evidence chunks
  -> Benzimidazoles rule extraction
  -> normalization
  -> strict validation
  -> ChemX-compatible CSV/JSON export
  -> local evaluation
  -> Streamlit review UI
```

## Компоненты runtime

`pdf_extraction` разбирает PDF в текстовые блоки, таблицы и provenance. В
финальном результате используются текст и таблицы; image-based structure
recognition не является частью публичного пути.

`datacon_workflow.extraction` строит evidence chunks и применяет правила для
`Benzimidazoles`. Финальный extractor покрывает:

- MIC/pMIC фрагменты в тексте;
- table-like MIC evidence, где единицы находятся в заголовке или названии
  таблицы;
- компактные/OCR формы единиц, например `µmolmL−1`, `µg mL−1`, `mg L−1`;
- antibacterial tables с compound ID вида `BK-1` ... `BK-11`, только для
  поддержанных колонок `S. aureus` и `E. coli`;
- компактные antimicrobial tables с заголовками вроде `Bc Sa Pa Ec Ab Ca`,
  где в финальный CSV попадают только поддержанные `Sa` и `Ec`.

`datacon_workflow.normalization` приводит значения к экспортному виду, не
перезаписывая raw evidence и не придумывая отсутствующие поля.

`datacon_workflow.validation` сохраняет строгую проверку: запись экспортируется
только если обязательные значения подтверждены evidence. Отсутствующие значения
остаются `NOT_DETECTED`, неподдержанные записи отклоняются.

`datacon_workflow.export` пишет ChemX-compatible CSV с точным порядком колонок:

```text
compound_id,smiles,target_type,target_relation,target_value,target_units,bacteria
```

Финальная дедупликация evidence-aware: одинаковые ChemX-строки объединяются
только если они пришли из одного `evidence_id`; повторные упоминания из разных
контекстов сохраняются.

`datacon_workflow.review_records` пишет sidecar-файлы
`review_records.csv` и `review_records.json`. Они связывают публичные строки с
source context, страницей, evidence text, extractor, confidence, compound
mentions и duplicate status. Эти review-поля не добавляются в публичный
`predictions.csv`.

`datacon_workflow.evaluation` считает локальные precision, recall, F1 и
Macro-F1. Per-article evaluation использует PDF stem для выбора ground truth.
Canonicalization чисел и алиасов бактерий применяется только в метриках и не
меняет extraction/export.

`app.py` предоставляет Streamlit review UI:

- просмотр сохраненного полного запуска;
- просмотр сохраненного additional domain `Synergy`, если его artifacts есть в
  `outputs/synergy_full/`;
- rules-only запуск одной статьи для выбранного домена;
- полный запуск датасета после подтверждения.

## Final Results

| Domain | Role | Output | Macro-F1 | Baseline | Improvement |
|---|---|---|---:|---:|---:|
| Benzimidazoles | Primary | `outputs/benzimidazoles_full` | `0.4622` | `0.217` | `~2.13x` |
| Synergy | Additional | `outputs/synergy_full` | `0.3626` | `0.080` | `~4.53x` |

Metrics are reported per domain. The repository local evaluator is used for
reproducible comparison and official scorer parity is not claimed.

## Финальная команда

```powershell
.\.venv\Scripts\python.exe scripts\run_benzimidazoles_full.py `
  --pdf-dir data\chemx\benzimidazoles\pdfs `
  --ground-truth data\chemx\benzimidazoles\ground_truth.csv `
  --output-dir outputs\benzimidazoles_full `
  --llm-mode never
```

Primary Domain: `Benzimidazoles`.

Финальный сохраненный результат:

```text
outputs/benzimidazoles_full/
Macro-F1: 0.4622
Published single-agent baseline: 0.217
Predictions: 2247
Ground-truth rows: 1721
PDFs completed: 31/31 locally available
```

## Additional Domain: Synergy

`Synergy` добавлен как отдельный additional domain rules-first результат.

Сохраненный результат:

```text
outputs/synergy_full/
Macro-F1: 0.3626
Published single-agent baseline: 0.080
Predictions: 6647
Ground-truth rows: 3089
Selected PDFs: 81
Failed article rows: 0
```

Команда:

```powershell
.\.venv\Scripts\python.exe scripts\run_synergy_experimental.py `
  --pdf-dir data\chemx\synergy\pdfs `
  --ground-truth data\chemx\synergy\ground_truth.csv `
  --output-dir outputs\synergy_full
```

`Synergy` имеет 42-колоночную схему и требует связывать nanoparticle, drug,
organism, method, dose/concentration и measured effect. Результат превышает
baseline в локальном evaluator, но из-за широкой схемы показывается отдельно и
имеет более шумный prediction-to-GT profile.

## Инварианты

- Этапы остаются разделенными: extraction, normalization, validation, export,
  evaluation.
- Provenance сохраняется: файл, страница, table/text context, метод и
  confidence, когда они доступны.
- Ground truth, прошлые predictions, metrics, replay batches и
  benchmark-derived fixes не используются как вход extraction.
- Validation не ослабляется ради метрик.
- Финальный rules-only запуск не делает LLM-вызовов.

## Экспериментальные части вне финального claim

В репозитории могут оставаться внутренние материалы и код для RAG, LLM fallback,
hybrid workflow, agentic sidecars, MolScribe, DECIMER, YOLO, OCR/image
pipeline и других structure-recognition экспериментов. Они не требуются для
публичного результата `Benzimidazoles` и не входят в финальные метрики.

