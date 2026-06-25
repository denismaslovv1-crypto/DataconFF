Самый простой путь: хранить не ссылки руками, а **список молекул** в CSV, а ссылки NIST генерировать автоматически.

### 1. Создай файл `input/molecules.csv`

```csv
name
Caffeine
Aspirin
Ibuprofen
Paracetamol
Naproxen
Diclofenac
Ketoprofen
Ethanol
Acetone
Glucose
Sucrose
Citric acid
Lactic acid
Alanine
Glycine
Phenylalanine
```

### 2. Замени `URLS = [...]` на чтение из файла

```python
from pathlib import Path
from urllib.parse import urlencode

INPUT_PATH = Path("input/molecules.csv")
BASE_NIST_SEARCH_URL = "https://webbook.nist.gov/cgi/cbook.cgi"


def build_nist_url_by_name(name):
    query = urlencode({"Name": name})
    return f"{BASE_NIST_SEARCH_URL}?{query}"


molecules_df = pd.read_csv(INPUT_PATH)

URLS = [
    build_nist_url_by_name(name)
    for name in molecules_df["name"].dropna().unique()
]
```

Теперь ты расширяешь датасет просто добавлением строк в `molecules.csv`.

### 3. Лучше сразу добавить CAS как более точный вариант

```csv
name,cas
Caffeine,58-08-2
Aspirin,50-78-2
Ibuprofen,15687-27-1
Paracetamol,103-90-2
Ethanol,64-17-5
Acetone,67-64-1
```

И генератор ссылок:

```python
def build_nist_url(row):
    if pd.notna(row.get("cas")) and str(row["cas"]).strip():
        return f"{BASE_NIST_SEARCH_URL}?ID=C{str(row['cas']).replace('-', '')}"

    return build_nist_url_by_name(row["name"])
```

Но для NIST **по имени надёжнее на старте**, потому что `ID=C...` не всегда очевидно совпадает с CAS без дефисов.

### 4. Практичный стартовый список

Для первого расширения возьми 50–100 простых молекул из категорий:

```text
лекарства: Caffeine, Aspirin, Ibuprofen, Paracetamol, Naproxen
растворители: Ethanol, Methanol, Acetone, Benzene, Toluene
сахара: Glucose, Fructose, Sucrose, Lactose
аминокислоты: Glycine, Alanine, Valine, Leucine, Phenylalanine
органические кислоты: Acetic acid, Citric acid, Lactic acid, Benzoic acid
```

### 5. Логика на будущее

```text
input/molecules.csv
        ↓
генерируем NIST URL
        ↓
парсим NIST
        ↓
по InChIKey идём в PubChem
        ↓
сохраняем compounds_dataset.csv
```

Так ты не привязан к ручному списку URL и можешь быстро наращивать датасет.
