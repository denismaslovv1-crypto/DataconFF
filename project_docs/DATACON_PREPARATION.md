# Datacon Extraction — передача проекта специалисту

_Состояние проверено 26 июня 2026 г._

## 1. Назначение проекта

**Datacon Extraction** — локальный Python-проект для извлечения химических
данных из научных источников и подготовки проверяемого датасета. Его конечная
цель — не чат по документам, а система, которая собирает данные из PDF, веба и
API, связывает структуры с экспериментальными свойствами, нормализует и
валидирует их, а затем помогает отбирать молекулы по заданным свойствам.

Ближайший работающий сценарий:

```text
научный PDF → текст/таблицы/изображения → сырые записи с provenance → CSV/JSON
```

Дальняя цель — многоагентный контур для сбора, извлечения, нормализации,
проверки и экспорта химических данных. Агентам нельзя разрешать выдумывать
структуры или подменять исходные данные: любое итоговое значение должно быть
связано с первоисточником.

Вне рамок проекта: аудиотранскрибация.

## 2. Главный принцип данных

Сырые извлечения, нормализация и валидация — независимые, необратимо не
смешиваемые стадии. Raw-данные никогда не перезаписываются результатом
нормализации или решения агента.

Минимальная provenance-цепочка для каждого значения:

```text
source file → page → section/table/figure → row (если есть)
→ extraction method → confidence
```

Для потенциальных химических записей уже предусмотрены: имя, формула,
молекулярная масса, SMILES/canonical/isomeric SMILES, InChI/InChIKey, CAS,
метка соединения в статье, свойство, значение, единица, confidence и статус
валидации.

## 3. Что реально реализовано

### RAG (`src/rag_core`)

Реализован единый RAG-слой с четырьмя логическими коллекциями:

| Коллекция | Содержимое | Роль |
| --- | --- | --- |
| `project_docs` | архитектура, решения, roadmap | источник правил и состояния |
| `methodology_notes` | PDF/OCR/химия/валидация | методическая память |
| `code_examples` | примеры парсеров | шаблоны реализации |
| `molecule_facts` | факты и датасеты | только фактические запросы |

Локальная реализация индексирует Markdown и разрешённые исходники в
heading-aware JSONL-чанки и ищет их BM25-подобным lexical retriever. Каждый
результат возвращает collection, путь, заголовок, диапазон строк, score и
совпавшие термины. Это работает офлайн.

Дополнительно подготовлен опциональный vector backend: Chroma + embeddings по
OpenAI-compatible API. Настройка находится в `config/rag_models.json`; ключи
не хранятся в Git и берутся из `.env`. Указаны OpenModel/DeepSeek для LLM и
OpenRouter/NVIDIA Nemotron для embeddings. Это не отдельная RAG-система, а
альтернативный backend того же контракта.

Артефакты индекса уже есть в `rag_index/` (JSONL/manifest и Chroma store).

### PDF extraction (`src/pdf_extraction`)

Реализован модульный pipeline и CLI `python -m pdf_extraction` / `datacon-pdf`.
Основные стадии:

1. `pdfplumber` извлекает постраничный текст и таблицы.
2. `ChemistryRecordExtractor` эвристически находит строки с меткой соединения
   и численными assay/property-значениями в таблицах и table-like тексте.
3. Экспортируется raw JSON на PDF, общий `chemical_records.csv` и
   `compound_labels.csv` — очередь меток соединений, которым ещё нужно
   сопоставить структуру.
4. Необязательные стадии допускают извлечение изображений, выделение структур,
   распознавание, enrichment и validation через заменяемые адаптеры.

Pipeline композиционный (`PdfPipelineComponents`), а тяжёлые интеграции по
умолчанию выключены Null-адаптерами. Это хороший фундамент для замены
эвристик/моделей без переписывания orchestration.

### Изображения и химические структуры

Поддержаны следующие контракты и утилиты:

- PyMuPDF: рендер страниц, ручной crop PDF-региона, sidecar с bbox и source;
- внешний детектор структур: JSON manifest (предполагается YOLO или DECIMER);
- внешний recognizer: MolScribe, OSRA; интерфейс reaction recognition для
  RxnScribe;
- импорт результата MolScribe обратно в JSON и CSV;
- автоматический workflow: base parser → page render → DECIMER segmentation →
  MolScribe → import.

Отдельные виртуальные окружения существуют для основного проекта, MolScribe и
DECIMER. Внешние модели/инструменты не vendored и не должны быть обязательными
для базового pipeline.

Критическое доменное правило: SMILES с wildcard (`*`) и схемы с `R/R1/R2/Ar`
являются **generic scaffold**, а не идентифицированной молекулой. Они помечаются
`is_generic_structure=True`, `generic_structure_unresolved`; нельзя связать их
с compound label как с окончательно решённой структурой. Связь допускается
только после source-backed извлечения заместителей из таблицы, текста или
подписи. Значения IC50/binding около рисунка — отдельные property records.

### Веб-источники

Есть черновой, не встроенный в core пример
`code_examples/Datacon_web_extraction/parser_nist.py`. Он ищет соединения в
NIST WebBook, обогащает по PubChem PUG REST через InChIKey и выгружает
formula/MW/SMILES/InChI/CAS/CID и ряд дескрипторов. Это полезный прототип
поставщика фактов, но пока монолитен, использует относительные пути и не имеет
общего контракта provenance/нормализации.

## 4. Фактические артефакты и качество

В `data/pdf_raw` находится 8 PDF, для каждого есть raw JSON в
`data/pdf_parsed`. На момент проверки их содержимое:

| Документ | Страниц | Таблиц | Raw records | Structures |
| --- | ---: | ---: | ---: | ---: |
| `1-s2.0-S0223523412000402-main` | 11 | 0 | 5 | 5 |
| `1-s2.0-S0960894X08008214-main` | 3 | 2 | 223 | 3 |
| `1-s2.0-S0960894X09003679-main` | 5 | 7 | 327 | 7 |
| `1-s2.0-S0960894X09006222-main` | 4 | 1 | 196 | 0 |
| `1-s2.0-S0960894X09006258-main` | 5 | 5 | 210 | 0 |
| naltrexamine article | 12 | 0 | 116 | 0 |
| neuropeptide-S article | 4 | 0 | 4 | 0 |
| dibenzothiazepines article | 8 | 0 | 0 | 0 |

Это демонстрационные raw-кандидаты, не валидированный эталонный датасет.
Нулевые таблицы/records не означают отсутствие информации в статье: сейчас
извлечение зависит от доступности текстового слоя, табличной разметки и узкой
эвристики строк.

Есть 24 unit-теста: RAG, пути, модели и компоненты PDF pipeline, экспорт,
эвристический chemistry extractor, bbox/page rendering, import crop,
external recognizer и mapping структур. Проверка 26.06.2026:

```text
24 passed
```

Единственное предупреждение — среда не смогла перезаписать существующий
`.pytest_cache`; на результаты тестов оно не влияет.

## 5. Чего пока нет — ключевой технический долг

- Семантика PDF ограничена `pdfplumber` + regex-эвристиками; layout analysis,
  OCR fallback, graph/chart extraction и устойчивое выделение figure captions
  не реализованы.
- Полноценные normalizer, RDKit-based validator и identifier enrichment пока
  представлены только интерфейсами/Null-адаптерами.
- Нет модели сущностей, связывающей `compound label → depiction → substituent
  definition → resolved structure → assay measurement` с evidence edges.
- Нет хранилища/схемы для normalized records, конфликта значений, review queue,
  versioning и утверждений пользователя.
- Нет orchestration, state machine, agent contracts, наблюдаемости,
  eval-набора и ручного review UI.
- `ROADMAP.md` описывает PDF extraction как planned, хотя MVP уже реализован;
  документ нужно обновить, чтобы он не вводил новых специалистов в заблуждение.
- В README встречаются команды с `python`/`py`, но проектная политика требует
  запускать конкретный интерпретатор (`.\\.venv\\Scripts\\python.exe`), а
  тяжёлые средства — из их выделенной venv.

## 6. Рекомендуемый новый подход к multi-agent системе

Не строить «свободный рой агентов». Нужна наблюдаемая workflow-система с
детерминированным состоянием, где агенты выполняют узкие задачи и создают
проверяемые артефакты. Оркестратор должен работать как DAG/state machine и
переиспользовать существующие Python-компоненты.

```text
Ingest
  → Parse (детерминированный PDF pipeline)
  → Evidence extraction (таблицы, фигуры, OCR)
  → Entity resolution (labels ↔ structures ↔ identifiers)
  → Normalize
  → Validate / conflict detection
  → Human review queue
  → Approved dataset export
```

Предлагаемые роли агентов:

| Агент | Вход | Выход | Жёсткое ограничение |
| --- | --- | --- | --- |
| Retrieval/planner | задача, RAG chunks | plan с citations | не читает весь corpus без retrieval |
| Extraction analyst | raw PDF artefacts | доп. кандидаты + evidence | не меняет raw records |
| Structure resolver | crop/scaffold/таблица | relation hypotheses | wildcard не становится molecule identity |
| Normalizer | raw candidates | versioned normalized records | хранит ссылку на raw/evidence |
| Validator | normalized record | issues/status/conflicts | не исправляет значение молча |
| Review coordinator | warning/conflict queue | запрос человеку/решение | не утверждает низкоуверенные данные |
| Exporter | approved dataset | CSV/JSON/Parquet + manifest | экспортирует только утверждённые версии |

LLM полезен для планирования, interpretation captions/таблиц, сопоставления
evidence и подготовки review-пакетов. Он не должен быть источником чисел,
SMILES или provenance: эти утверждения обязаны иметь ссылку на детерминированно
извлечённый фрагмент либо на внешний ответ API с сохранённым запросом/ответом.

Практичный следующий инкремент — не все агенты сразу, а **evidence graph +
review queue** поверх уже существующего raw JSON. После этого можно добавить
ровно два управляемых исполнителя: `normalization/validation` и
`structure-label resolution`. Это даст пользу без размножения сущностей и
позволит измерять точность до внедрения LLM-orchestration.

## 7. Что передать новому специалисту

1. Репозиторий целиком, включая `src/`, `tests/`, `data/pdf_parsed/`,
   `data/molecule_crops*` и `rag_index/`; `.env` не передавать публично.
2. Этот файл, `AGENTS.MD`, `README.md`, `project_docs/DECISIONS.md`,
   `project_docs/RAG_DESIGN.md` и `project_docs/PDF_EXTRACTION_PLAN.md`.
3. Уточнение, что старый roadmap отстаёт от кода: RAG и raw PDF pipeline уже
   существуют, но downstream data lifecycle ещё нет.
4. Вопросы для архитектурного решения: выбрать persistent store для evidence
   graph/records; формат approval/versioning; набор golden PDFs и метрики;
   границу human review; допустимые внешние API и модель/стоимость LLM.

## 8. Рабочая среда

- Python >= 3.11, фактически использовался `.venv` на Python 3.12.13.
- Базовые зависимости: Pydantic, pdfplumber, OpenAI SDK, pytest.
- Опционально: Chroma, PyMuPDF, Ultralytics; отдельные venv для MolScribe и
  DECIMER.
- Главные команды следует запускать так:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pdf_extraction data\pdf_raw --output-dir data\pdf_parsed
.\.venv\Scripts\python.exe -m rag_core query "PDF table extraction provenance"
```

Не использовать системный Python/Codex runtime как неявный fallback и не
устанавливать зависимости без отдельного решения владельца проекта.
