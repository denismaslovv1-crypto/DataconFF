````markdown
# NIST + PubChem Molecule Dataset Builder

Проект для автоматического сбора и обогащения данных о химических соединениях.

На вход подается список молекул, после чего программа:

1. Находит молекулу в NIST Chemistry WebBook.
2. Извлекает основные химические идентификаторы.
3. Переходит в PubChem через InChIKey.
4. Получает структурные дескрипторы молекулы.
5. Сохраняет результат в CSV, Excel и JSON.

---

# Архитектура

```text
Список молекул
       │
       ▼
NIST Chemistry WebBook
       │
       ├── Name
       ├── Formula
       ├── Molecular Weight
       ├── InChI
       ├── InChIKey
       ├── CAS Number
       ├── 2D Mol URL
       └── 3D Mol URL
       │
       ▼
PubChem
       │
       ├── CID
       ├── SMILES
       ├── LogP
       ├── TPSA
       ├── H-bond Donors
       ├── H-bond Acceptors
       └── Rotatable Bonds
       │
       ▼
Dataset
(CSV / XLSX / JSON)
```

---

# Используемые источники

## NIST Chemistry WebBook

Источник базовых химических данных:

- название вещества
- молекулярная формула
- молекулярная масса
- InChI
- InChIKey
- CAS номер
- 2D MOL файл
- 3D SD файл

Пример страницы:

https://webbook.nist.gov/cgi/cbook.cgi?Name=Caffeine

---

## PubChem

Источник структурных дескрипторов:

- CID
- SMILES
- LogP
- TPSA
- H-Bond Donor Count
- H-Bond Acceptor Count
- Rotatable Bond Count

Пример:

https://pubchem.ncbi.nlm.nih.gov/compound/2519

---

# Структура проекта

```text
project/
│
├── parser_nist.py
│
├── input/
│   └── molecules.csv
│
├── output/
│   ├── compounds_dataset.csv
│   ├── compounds_dataset.xlsx
│   └── compounds_dataset.json
│
└── README.md
```

---

# Входные данные

Файл:

```text
input/molecules.csv
```

Пример:

```csv
name
Caffeine
Aspirin
Ibuprofen
Paracetamol
Glucose
```

---

# Выходные данные

## CSV

```text
output/compounds_dataset.csv
```

## Excel

```text
output/compounds_dataset.xlsx
```

## JSON

```text
output/compounds_dataset.json
```

---

# Поля датасета

| Поле | Описание |
|--------|--------|
| name | Название вещества |
| formula | Химическая формула |
| mw | Молекулярная масса |
| inchi | InChI |
| inchikey | InChIKey |
| cas_number | CAS номер |
| pubchem_cid | PubChem CID |
| smiles | Canonical SMILES |
| isomeric_smiles | Isomeric SMILES |
| xlogp | Коэффициент распределения LogP |
| tpsa | Topological Polar Surface Area |
| hbond_donor_count | Количество доноров водородной связи |
| hbond_acceptor_count | Количество акцепторов водородной связи |
| rotatable_bond_count | Количество вращаемых связей |
| mol_2d_url | Ссылка на 2D Mol |
| mol_3d_url | Ссылка на 3D SD |
| nist_url | Страница NIST |
| pubchem_url | Страница PubChem |

---

# Зачем нужны дескрипторы

## H-Bond Donor Count

Количество групп, способных отдавать водородную связь.

Примеры:

- OH
- NH

Используется при оценке растворимости и проницаемости молекулы.

---

## H-Bond Acceptor Count

Количество атомов, способных принимать водородную связь.

Примеры:

- O
- N
- S

Используется в моделировании взаимодействия с белками.

---

## TPSA

Полярная поверхность молекулы.

Характеризует способность проникать через мембраны.

Часто используется в QSAR-моделях.

---

## LogP

Мера гидрофобности молекулы.

Показывает склонность вещества растворяться:

- в воде
- в жирах

Один из ключевых дескрипторов лекарственных молекул.

---

## Rotatable Bonds

Количество свободно вращающихся связей.

Показывает гибкость молекулы.

Используется при молекулярном докинге и QSAR.

---

# Возможные улучшения

## Этап 1

Добавить больше молекул.

Например:

- лекарственные вещества
- аминокислоты
- сахара
- органические кислоты

---

## Этап 2

Автоматический поиск молекул через PubChem.

Например:

- все антибиотики
- все аминокислоты
- все вещества с молекулярной массой < 500

---

## Этап 3

Добавить RDKit.

Позволит рассчитывать дополнительные признаки:

- Ring Count
- Aromatic Ring Count
- FractionCSP3
- Molecular Refractivity
- Morgan Fingerprints
- MACCS Keys

---

## Этап 4

Построение ML датасета.

Возможные задачи:

- классификация молекул
- кластеризация веществ
- поиск похожих соединений
- QSAR модели
- RAG по химическим данным

---

# Запуск

Установка зависимостей:

```bash
pip install requests pandas beautifulsoup4 openpyxl
```

Запуск:

```bash
python parser_nist.py
```

После выполнения результаты появятся в папке:

```text
output/
```

---

# Текущий статус

✅ Парсинг NIST

✅ Извлечение InChI и InChIKey

✅ Извлечение CAS

✅ Получение CID из PubChem

✅ Получение структурных дескрипторов

✅ Экспорт в CSV

✅ Экспорт в XLSX

✅ Экспорт в JSON

⬜ Автоматический сбор тысяч молекул

⬜ RDKit дескрипторы

⬜ Fingerprints

⬜ QSAR Dataset
````
