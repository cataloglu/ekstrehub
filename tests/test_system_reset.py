from app.system_reset import (
    CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE,
    CLEAR_LEARNED_RULES_CONFIRM_PHRASE,
    RESET_CONFIRM_PHRASE,
)


def test_reset_confirm_phrase_is_stable():
    assert RESET_CONFIRM_PHRASE == "SIFIRLA"


def test_clear_learned_rules_phrase_is_stable():
    assert CLEAR_LEARNED_RULES_CONFIRM_PHRASE == "KURALLAR"


def test_clear_email_ingestion_phrase_is_stable():
    assert CLEAR_EMAIL_INGESTION_CONFIRM_PHRASE == "POSTA"
