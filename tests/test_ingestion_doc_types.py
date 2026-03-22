from app.ingestion.service import MailIngestionService


def test_resolve_doc_type_from_extension() -> None:
    assert MailIngestionService._resolve_doc_type("ekstre.pdf", "application/octet-stream") == "pdf"
    assert MailIngestionService._resolve_doc_type("transactions.csv", "text/plain") == "csv"
    assert MailIngestionService._resolve_doc_type("image.jpg", "application/octet-stream") == "image"


def test_resolve_doc_type_from_content_type() -> None:
    assert MailIngestionService._resolve_doc_type("blob.bin", "application/pdf") == "pdf"
    assert MailIngestionService._resolve_doc_type("blob.bin", "text/csv") == "csv"
    assert MailIngestionService._resolve_doc_type("blob.bin", "image/png") == "image"


def test_resolve_doc_type_unknown() -> None:
    assert MailIngestionService._resolve_doc_type("notes.txt", "text/plain") == "other"


def test_detect_bank_name_from_sender_or_subject() -> None:
    assert (
        MailIngestionService._detect_bank_name("ekstre@notify.garanti.com", "Kredi Karti Ekstresi")
        == "Garanti BBVA"
    )
    assert MailIngestionService._detect_bank_name("notice@x.com", "YapiKredi Hesap Ozeti") == "Yapı Kredi"
    assert MailIngestionService._detect_bank_name("notice@x.com", "Random Subject") is None
