from pathlib import Path
import argparse

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def normalize_pdf_stem(value: str) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    text = text.replace("\\", "/").split("/")[-1]

    if text.lower().endswith(".pdf"):
        text = text[:-4]

    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        required=True,
        help="ChemX domain folder name: benzimidazoles or synergy",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional custom path to ground_truth.csv",
    )
    parser.add_argument(
        "--pdf-dir",
        default=None,
        help="Optional custom path to PDF folder",
    )

    args = parser.parse_args()

    base_dir = PROJECT_ROOT / "data" / "chemx" / args.domain

    csv_path = Path(args.csv) if args.csv else base_dir / "ground_truth.csv"
    pdf_dir = Path(args.pdf_dir) if args.pdf_dir else base_dir / "pdfs"
    missing_path = base_dir / "missing_pdfs.csv"

    pdf_dir.mkdir(parents=True, exist_ok=True)
    base_dir.mkdir(parents=True, exist_ok=True)

    if not csv_path.exists():
        raise RuntimeError(f"Ground truth file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if "pdf" not in df.columns:
        raise RuntimeError(
            f"Missing required column: pdf\n"
            f"File: {csv_path}\n"
            f"Available columns: {df.columns.tolist()}"
        )

    expected_pdf_stems = {
        normalize_pdf_stem(value)
        for value in df["pdf"].dropna().unique()
        if normalize_pdf_stem(value)
    }

    local_pdf_stems = {
        normalize_pdf_stem(path.name)
        for path in pdf_dir.glob("*.pdf")
    }

    missing_stems = sorted(expected_pdf_stems - local_pdf_stems)
    existing_expected_stems = sorted(expected_pdf_stems & local_pdf_stems)
    extra_local_stems = sorted(local_pdf_stems - expected_pdf_stems)

    missing_df = pd.DataFrame(
        {
            "pdf": missing_stems,
            "filename": [stem for stem in missing_stems],
        }
    )

    missing_df.to_csv(missing_path, index=False, encoding="utf-8")

    print(f"Domain: {args.domain}")
    print(f"Ground truth file: {csv_path}")
    print(f"PDF folder: {pdf_dir}")
    print(f"Expected unique PDFs: {len(expected_pdf_stems)}")
    print(f"Existing expected PDFs: {len(existing_expected_stems)}")
    print(f"Missing PDFs: {len(missing_stems)}")
    print(f"Extra local PDFs not in ground_truth: {len(extra_local_stems)}")
    print(f"Saved missing list: {missing_path}")

    if missing_stems:
        print("\nMissing files:")
        for stem in missing_stems:
            print(f"{stem}.pdf")

    if extra_local_stems:
        print("\nExtra local PDFs not found in ground_truth:")
        for stem in extra_local_stems:
            print(f"{stem}.pdf")


if __name__ == "__main__":
    main()


# run as
# .\.venv\Scripts\python.exe scripts\check_missing_pdfs.py --domain ...