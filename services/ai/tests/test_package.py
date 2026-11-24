import ai_doc_assistant


def test_package_exposes_version() -> None:
    assert ai_doc_assistant.__version__ == "0.1.0"
