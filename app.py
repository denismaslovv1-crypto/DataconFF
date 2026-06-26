"""Minimal review UI. Streamlit remains an optional UI dependency."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:
        raise RuntimeError("Streamlit is not installed. Install it manually in .venv to run the UI.") from exc
    from datacon_workflow.orchestrator import run_benzimidazole_workflow

    st.title("DataCon ChemX: Benzimidazoles")
    domain = st.selectbox("Domain", ["benzimidazoles"])
    uploaded = st.file_uploader("Scientific PDF", type=["pdf"])
    if uploaded is None or not st.button("Run extraction"):
        return
    with tempfile.TemporaryDirectory() as temporary_directory:
        pdf_path = Path(temporary_directory) / uploaded.name
        pdf_path.write_bytes(uploaded.getvalue())
        output_dir = Path(temporary_directory) / "outputs" / domain
        state = run_benzimidazole_workflow(pdf_path, output_dir)
        rows = [record.chemx_row() for record in state.normalized_records]
        st.dataframe(rows)
        if state.validation_errors:
            st.warning("\n".join(state.validation_errors))
        st.json([record.model_dump(mode="json") for record in state.normalized_records])
        st.download_button("Download CSV", state.prediction_csv.read_bytes(), "predictions.csv", "text/csv")
        st.download_button("Download JSON", state.prediction_json.read_bytes(), "predictions.json", "application/json")


if __name__ == "__main__":
    main()
