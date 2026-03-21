from app.system_reset import RESET_CONFIRM_PHRASE


def test_reset_confirm_phrase_is_stable():
    assert RESET_CONFIRM_PHRASE == "SIFIRLA"
