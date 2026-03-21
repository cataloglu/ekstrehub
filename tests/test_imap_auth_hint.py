"""IMAP auth error classification for user-facing messages."""

from app.main import _imap_auth_failed_user_message, _imap_error_is_invalid_credentials


def test_imap_error_detects_authentication_failed() -> None:
    raw = "b'[AUTHENTICATIONFAILED] Invalid credentials (Failure)'"
    assert _imap_error_is_invalid_credentials(raw)


def test_imap_auth_message_is_non_empty() -> None:
    assert "Uygulama şifresi" in _imap_auth_failed_user_message() or "uygulama" in _imap_auth_failed_user_message().lower()
