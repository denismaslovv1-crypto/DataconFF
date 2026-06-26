from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE_DIR = PROJECT_ROOT / "data" / "chemx" / "benzimidazoles"
CSV_PATH = BASE_DIR / "ground_truth.csv"
PDF_DIR = BASE_DIR / "pdfs"
MISSING_PATH = BASE_DIR / "missing_pdfs.csv"

UNPAYWALL_EMAIL = "your_email@example.com"

PDF_DIR.mkdir(parents=True, exist_ok=True)


def safe_name(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
        .replace("?", "_")
        .replace("&", "_")
        .replace("=", "_")
    )


def is_pdf_response(response: requests.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "pdf" in content_type or response.content.startswith(b"%PDF")


def download_pdf(url: str, out_path: Path) -> bool:
    response = requests.get(
        url,
        timeout=40,
        headers={"User-Agent": "Mozilla/5.0"},
        allow_redirects=True,
    )
    response.raise_for_status()

    if not is_pdf_response(response):
        return False

    out_path.write_bytes(response.content)
    return True


def get_unpaywall_pdf_url(doi: str) -> str | None:
    if not doi or doi == "nan":
        return None

    api_url = f"https://api.unpaywall.org/v2/{doi}"
    response = requests.get(
        api_url,
        params={"email": UNPAYWALL_EMAIL},
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    if response.status_code != 200:
        return None

    data = response.json()

    best = data.get("best_oa_location") or {}
    pdf_url = best.get("url_for_pdf")
    if pdf_url:
        return pdf_url

    for location in data.get("oa_locations") or []:
        pdf_url = location.get("url_for_pdf")
        if pdf_url:
            return pdf_url

    return None


df = pd.read_csv(CSV_PATH)

required_columns = ["doi", "title"]
for col in required_columns:
    if col not in df.columns:
        raise RuntimeError(f"Missing required column: {col}")

columns = ["doi", "title"]
if "pdf" in df.columns:
    columns.insert(0, "pdf")

sources = df[columns].drop_duplicates()

missing = []
downloaded = 0

for _, row in sources.iterrows():
    doi = str(row.get("doi", "")).strip()
    title = str(row.get("title", "")).strip()
    pdf_value = str(row.get("pdf", "")).strip() if "pdf" in sources.columns else ""

    out_name = safe_name(doi) if doi and doi != "nan" else safe_name(title[:80])
    out_path = PDF_DIR / f"{out_name}.pdf"

    if out_path.exists():
        print(f"exists: {out_path}")
        continue

    candidate_urls = []

    if pdf_value.startswith(("http://", "https://")):
        candidate_urls.append(pdf_value)

    unpaywall_url = get_unpaywall_pdf_url(doi)
    if unpaywall_url:
        candidate_urls.append(unpaywall_url)

    success = False

    for url in candidate_urls:
        try:
            if download_pdf(url, out_path):
                print(f"saved: {out_path}")
                downloaded += 1
                success = True
                break
            else:
                print(f"not pdf: {url}")
        except Exception as e:
            print(f"failed: {url} | {e}")

    if not success:
        missing.append(
            {
                "pdf": pdf_value,
                "doi": doi,
                "title": title,
                "reason": "no_open_pdf_found",
            }
        )

if missing:
    pd.DataFrame(missing).to_csv(MISSING_PATH, index=False)
    print(f"Saved missing list: {MISSING_PATH}")

print(f"Downloaded PDFs: {downloaded}")
print(f"Missing PDFs: {len(missing)}")