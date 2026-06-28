# Результаты

Финальный проверенный rules-only запуск для `Benzimidazoles`:

```text
outputs/benzimidazoles_full/
```

Он обработал локально доступный набор PDF и превысил опубликованный
single-agent baseline в локальном evaluator репозитория.

## Сводка

| Метрика | Значение |
|---|---:|
| Домен | Benzimidazoles |
| Режим | rules-only |
| PDF обработано | 31/31 локально доступных |
| Строк предсказаний | 2247 |
| Строк ground truth | 1721 |
| Macro-F1 локального evaluator | 0.4622 |
| Опубликованный single-agent baseline | 0.217 |

## Experimental Second Domain: Synergy

Отдельно от финального `Benzimidazoles` результата сохранен экспериментальный
rules-first MVP для `Synergy`:

```text
outputs/synergy_full/
```

| Метрика | Значение |
|---|---:|
| Домен | Synergy |
| Статус | experimental second domain |
| PDF выбрано | 81 |
| Ground-truth PDF identities | 80 |
| Строк предсказаний | 6647 |
| Строк local ground truth | 3089 |
| Macro-F1 локального evaluator | 0.3626 |
| Опубликованный single-agent baseline | 0.080 |
| Улучшение над baseline | около 4.53x |
| Failed article rows | 0 |

`Synergy` не является основным стабильным доменом. Результат превышает
опубликованный baseline в локальном evaluator, но схема шире
(`42` колонки), а результат остается экспериментальным вторым доменом.
Поэтому его можно показывать без claim о полном решении `Synergy` или parity с
официальным scorer.

## Метрики по полям

Из `outputs/benzimidazoles_full/field_metrics.csv`:

| Поле | Precision | Recall | F1 | True positive |
|---|---:|---:|---:|---:|
| compound_id | 0.1713 | 0.2237 | 0.1941 | 385 |
| smiles | 0.0000 | 0.0000 | 0.0000 | 0 |
| target_type | 0.7459 | 0.9739 | 0.8448 | 1676 |
| target_relation | 0.7183 | 0.9378 | 0.8135 | 1614 |
| target_value | 0.3427 | 0.4474 | 0.3881 | 770 |
| target_units | 0.5376 | 0.7019 | 0.6089 | 1208 |
| bacteria | 0.3409 | 0.4451 | 0.3861 | 766 |

## Что улучшено

Финальный rules-only путь включает несколько source-backed улучшений:

- `target_units` извлекаются из того же evidence context, включая заголовки
  таблиц и компактные формы вроде `MIC=12.5µmolmL−1`;
- поддержаны antibacterial MIC таблицы с compound ID вида `BK-1` ... `BK-11`,
  при этом экспортируются только поддержанные `S. aureus` и `E. coli`;
- поддержаны компактные antimicrobial tables с organism abbreviations вроде
  `Bc Sa Pa Ec Ab Ca`; финальный extractor берет только `Sa` и `Ec`;
- export-дедупликация учитывает `evidence_id`, поэтому повторные source-backed
  упоминания из разных контекстов не теряются;
- `review_records.csv/.json` связывают prediction rows с source context,
  evidence id, extractor, confidence и duplicate diagnostics без изменения
  публичной ChemX-схемы.

## Consistency evaluation

Per-article evaluation выбирает ground truth по PDF stem. DOI из текста может
использоваться как вспомогательная metadata, но не как единственный фильтр:
reference sections и ошибки парсинга DOI могут приводить к неверному
`gt_rows`.

В evaluator есть metric-only canonicalization:

- числовые сериализации `5`, `5.0`, `5.00` сравниваются как одно значение;
- алиасы бактерий вроде `S. aureus` / `Staphylococcus aureus` и
  `E. coli` / `Escherichia coli` сравниваются как одно значение.

Эта canonicalization применяется только при сравнении метрик. Она не меняет
raw extraction, validation или экспортируемые evidence.

## Caveats

- Локальный evaluator является приближением; совпадение с официальным scorer
  не заявляется.
- Финальный claim относится только к `Benzimidazoles`.
- `Synergy` является экспериментальным вторым доменом и не заменяет финальный
  `Benzimidazoles` claim.
- Финальный public run rules-only и не делает LLM-вызовов.
- SMILES не решены: поле `smiles` остается `NOT_DETECTED`, F1 `0.0000`.
- Image/structure recognition не использовался в финальной оценке.
- Recall ограничен, качество неравномерно между статьями.

## Streamlit review UI

Streamlit-приложение является review-интерфейсом, а не чатботом. Оно позволяет:

- открыть сохраненный full-run и посмотреть aggregate metrics,
  article summary, field metrics, predictions, evidence/review context,
  duplicate diagnostics и downloads;
- запустить одну статью в rules-only режиме и проверить provenance;
- запустить полный датасет через documented command после явного
  подтверждения.

