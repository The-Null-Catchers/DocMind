from __future__ import annotations

import smtplib

import pytest

from app.config import Settings
from app.services import email as email_service


class FakeSMTP:
    sent = []
    logged_in = None
    started_tls = False

    def __init__(self, host: str, port: int, timeout: int):
        self.host = host
        self.port = port
        self.timeout = timeout

    def ehlo(self) -> None:
        return None

    def starttls(self) -> None:
        type(self).started_tls = True

    def login(self, username: str, password: str) -> None:
        type(self).logged_in = (username, password)

    def send_message(self, message) -> None:
        type(self).sent.append(message)

    def quit(self) -> None:
        return None


def test_production_requires_smtp_email_backend():
    with pytest.raises(ValueError, match="EMAIL_BACKEND"):
        Settings(
            app_env="production",
            app_secret="x" * 48,
            database_url="postgresql+psycopg://user:pass@db/docmind",
            storage_backend="local",
            llm_provider="mock",
            embedding_provider="hash",
            email_backend="console",
        )


def test_smtp_password_reset_delivery(monkeypatch):
    FakeSMTP.sent = []
    FakeSMTP.logged_in = None
    FakeSMTP.started_tls = False
    settings = Settings(
        email_backend="smtp",
        email_from="DocMind <noreply@example.com>",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="docmind",
        smtp_password="secret",
        smtp_use_tls=True,
        web_origin="https://docmind.example.com",
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: settings)
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)

    email_service.send_password_reset_email("person@example.com", "token+/=")

    assert len(FakeSMTP.sent) == 1
    message = FakeSMTP.sent[0]
    assert message["To"] == "person@example.com"
    assert message["From"] == "DocMind <noreply@example.com>"
    assert "token%2B%2F%3D" in message.as_string()
    assert FakeSMTP.started_tls is True
    assert FakeSMTP.logged_in == ("docmind", "secret")


def test_smtp_failure_is_not_silently_accepted(monkeypatch):
    settings = Settings(
        email_backend="smtp",
        email_from="noreply@example.com",
        smtp_host="smtp.example.com",
    )
    monkeypatch.setattr(email_service, "get_settings", lambda: settings)

    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("network down")

    monkeypatch.setattr(smtplib, "SMTP", BrokenSMTP)
    with pytest.raises(email_service.EmailDeliveryError):
        email_service.send_verification_email("person@example.com", "token")
