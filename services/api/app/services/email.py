from __future__ import annotations

import smtplib
from email.message import EmailMessage
from html import escape
from urllib.parse import quote

from ..config import Settings, get_settings


class EmailDeliveryError(RuntimeError):
    """Raised when a configured email provider cannot deliver a message."""


def _absolute_web_url(path: str, settings: Settings) -> str:
    return f"{settings.web_origin.rstrip('/')}/{path.lstrip('/')}"


def _deliver(*, to: str, subject: str, text: str, html: str | None = None) -> None:
    settings = get_settings()
    backend = settings.email_backend.lower()

    if backend == "console":
        # Development-only transport. Never selected by validated production settings.
        print(f"[docmind-email] to={to} subject={subject}\n{text}")
        return
    if backend != "smtp":
        raise EmailDeliveryError(f"Unsupported EMAIL_BACKEND={settings.email_backend}")

    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    if html:
        message.add_alternative(html, subtype="html")

    try:
        if settings.smtp_use_tls:
            client: smtplib.SMTP = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            )
            client.ehlo()
            client.starttls()
            client.ehlo()
        else:
            client = smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            )
        try:
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
        finally:
            client.quit()
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Configured SMTP delivery failed") from exc


def send_password_reset_email(email: str, token: str) -> None:
    settings = get_settings()
    url = _absolute_web_url(
        f"reset-password?token={quote(token, safe='')}",
        settings,
    )
    text = (
        "Reset your DocMind password using the link below. "
        "This link expires in 30 minutes.\n\n"
        f"{url}\n\n"
        "If you did not request this, you can ignore this message."
    )
    _deliver(
        to=email,
        subject="Reset your DocMind password",
        text=text,
        html=(
            "<p>Reset your DocMind password using the link below. "
            "This link expires in 30 minutes.</p>"
            f'<p><a href="{escape(url, quote=True)}">Reset password</a></p>'
            "<p>If you did not request this, you can ignore this message.</p>"
        ),
    )


def send_verification_email(email: str, token: str) -> None:
    settings = get_settings()
    url = _absolute_web_url(
        f"verify-email?token={quote(token, safe='')}",
        settings,
    )
    _deliver(
        to=email,
        subject="Verify your DocMind email",
        text=f"Verify your DocMind email address within 24 hours:\n\n{url}",
        html=(
            "<p>Verify your DocMind email address within 24 hours.</p>"
            f'<p><a href="{escape(url, quote=True)}">Verify email</a></p>'
        ),
    )


def send_workspace_invitation_email(
    *,
    email: str,
    workspace_name: str,
    role: str,
) -> None:
    settings = get_settings()
    url = _absolute_web_url("app/settings", settings)
    safe_workspace = escape(workspace_name)
    safe_role = escape(role)
    _deliver(
        to=email,
        subject=f"You were invited to {workspace_name} on DocMind",
        text=(
            f"You were invited to the DocMind workspace \"{workspace_name}\" "
            f"with the {role} role. Sign in or create an account with this email, "
            f"then open your invitation inbox:\n\n{url}"
        ),
        html=(
            f"<p>You were invited to the DocMind workspace <strong>{safe_workspace}</strong> "
            f"with the <strong>{safe_role}</strong> role.</p>"
            "<p>Sign in or create an account with this email, then open your invitation inbox.</p>"
            f'<p><a href="{escape(url, quote=True)}">Open DocMind invitations</a></p>'
        ),
    )
