from datacon_workflow.domains.synergy import _records_from_snippet


def test_synergy_text_rules_skip_context_only_mentions() -> None:
    records = list(
        _records_from_snippet(
            "Silver nanoparticles showed antibacterial activity against Escherichia coli.",
            "article.pdf",
            1,
            "text-1",
            {"pdf": "article.pdf"},
            {},
        )
    )

    assert records == []


def test_synergy_text_rules_keep_measured_activity() -> None:
    records = list(
        _records_from_snippet(
            "Ag nanoparticles had MIC of 8 ug/ml against Escherichia coli.",
            "article.pdf",
            1,
            "text-1",
            {"pdf": "article.pdf"},
            {},
        )
    )

    assert len(records) == 1
    assert records[0].row["NP"] == "Ag"
    assert records[0].row["bacteria"] == "Escherichia coli"
    assert records[0].row["method"] == "MIC"
    assert records[0].row["ZOI_NP_mm_or_MIC_np_µg_ml"] == "8"


def test_synergy_table_rules_keep_context_row_without_activity_measure() -> None:
    records = list(
        _records_from_snippet(
            "Silver nanoparticles showed antibacterial activity against Escherichia coli.",
            "article.pdf",
            1,
            "1",
            {"pdf": "article.pdf"},
            {},
            table_id="table-1",
            method_name="synergy.table_rules",
        )
    )

    assert len(records) == 1
    assert records[0].evidence.extraction_method == "synergy.table_rules"
