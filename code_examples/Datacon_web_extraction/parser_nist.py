import json
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.parse import urlencode

import pandas as pd
import requests
from bs4 import BeautifulSoup


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

BASE_URL = "https://webbook.nist.gov"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "DataconPyExtraction/1.0"})


def get_json_ld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
        except Exception:
            continue

        if data.get("@type") == "MolecularEntity":
            return data

    return {}


def find_text_after_label(soup, label):
    strong = soup.find("strong", string=lambda text: text and label in text)

    if not strong:
        return None

    li = strong.find_parent("li")
    text = li.get_text(" ", strip=True)

    return text.replace(label, "").replace(":", "").strip()


def parse_nist_page(url):
    response = session.get(url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    json_ld = get_json_ld(soup)

    mol_2d = soup.find("a", href=lambda href: href and "Str2File=" in href)
    mol_3d = soup.find("a", href=lambda href: href and "Str3File=" in href)

    h1 = soup.select_one("h1#Top")

    return {
        "name": json_ld.get("name") or (h1.get_text(strip=True) if h1 else None),
        "formula": json_ld.get("molecularFormula"),
        "mw": clean_amu(json_ld.get("molecularWeight")),
        "inchi": json_ld.get("inChI"),
        "inchikey": json_ld.get("inChIKey"),
        "cas_number": find_text_after_label(soup, "CAS Registry Number"),
        "mol_2d_url": urljoin(BASE_URL, mol_2d["href"]) if mol_2d else None,
        "mol_3d_url": urljoin(BASE_URL, mol_3d["href"]) if mol_3d else None,
        "nist_url": url,
    }


def clean_amu(value):
    if not value:
        return None

    return str(value).replace(" amu", "").strip()


def get_pubchem_cid_by_inchikey(inchikey):
    if not inchikey:
        return None

    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{inchikey}/cids/TXT"

    response = session.get(url, timeout=20)

    if response.status_code == 404:
        return None

    response.raise_for_status()

    text = response.text.strip()
    return text.splitlines()[0] if text else None


def get_pubchem_properties(cid):
    if not cid:
        return {}

    properties = [
        "MolecularFormula",
        "MolecularWeight",
        "CanonicalSMILES",
        "IsomericSMILES",
        "ConnectivitySMILES",
        "SMILES",
        "XLogP",
        "TPSA",
        "HBondDonorCount",
        "HBondAcceptorCount",
        "RotatableBondCount",
    ]

    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
        f"{cid}/property/{','.join(properties)}/JSON"
    )

    response = session.get(url, timeout=20)

    if response.status_code == 404:
        return {}

    response.raise_for_status()

    data = response.json()
    props = data["PropertyTable"]["Properties"][0]

    smiles = (
        props.get("CanonicalSMILES")
        or props.get("ConnectivitySMILES")
        or props.get("SMILES")
    )

    isomeric_smiles = props.get("IsomericSMILES") or smiles

    return {
        "pubchem_cid": props.get("CID"),
        "smiles": smiles,
        "isomeric_smiles": isomeric_smiles,
        "pubchem_formula": props.get("MolecularFormula"),
        "pubchem_mw": props.get("MolecularWeight"),
        "xlogp": props.get("XLogP"),
        "tpsa": props.get("TPSA"),
        "hbond_donor_count": props.get("HBondDonorCount"),
        "hbond_acceptor_count": props.get("HBondAcceptorCount"),
        "rotatable_bond_count": props.get("RotatableBondCount"),
        "pubchem_url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
    }


def parse_compound(url):
    nist_data = parse_nist_page(url)

    cid = get_pubchem_cid_by_inchikey(nist_data.get("inchikey"))
    time.sleep(0.2)

    pubchem_data = get_pubchem_properties(cid)
    time.sleep(0.2)

    return {
        **nist_data,
        **pubchem_data,
    }


rows = []

for url in URLS:
    try:
        print(f"Parsing: {url}")

        row = parse_compound(url)
        rows.append(row)

        print(
            f"OK: {row.get('name')} | "
            f"CID: {row.get('pubchem_cid')} | "
            f"SMILES: {row.get('smiles')}"
        )

    except Exception as e:
        print(f"ERROR: {url} -> {e}")


df = pd.DataFrame(rows)

column_order = [
    "name",
    "formula",
    "mw",
    "inchi",
    "inchikey",
    "cas_number",
    "pubchem_cid",
    "smiles",
    "isomeric_smiles",
    "xlogp",
    "tpsa",
    "hbond_donor_count",
    "hbond_acceptor_count",
    "rotatable_bond_count",
    "mol_2d_url",
    "mol_3d_url",
    "nist_url",
    "pubchem_url",
]

df = df.reindex(columns=column_order)

csv_path = OUTPUT_DIR / "compounds_dataset.csv"
xlsx_path = OUTPUT_DIR / "compounds_dataset.xlsx"
json_path = OUTPUT_DIR / "compounds_dataset.json"

df.to_csv(csv_path, index=False, encoding="utf-8-sig")
df.to_excel(xlsx_path, index=False)
df.to_json(json_path, orient="records", force_ascii=False, indent=4)

print("\nSaved files:")
print(csv_path.resolve())
print(xlsx_path.resolve())
print(json_path.resolve())

print("\nPreview:")
print(df)