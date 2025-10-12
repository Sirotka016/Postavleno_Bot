"""Helpers for sending verification emails."""

from __future__ import annotations

from email.message import EmailMessage

from aiosmtplib import SMTP


async def send_email(
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    sender_name: str,
    to_email: str,
    subject: str,
    body: str,
    timeout: int = 20,
) -> None:
    """Send an email using STARTTLS over SMTP."""

    message = EmailMessage()
    message["From"] = f"{sender_name} <{username}>"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    smtp = SMTP(hostname=host, port=port, start_tls=True, timeout=timeout)
    await smtp.connect()
    try:
        await smtp.starttls()
        await smtp.login(username, password)
        await smtp.send_message(message)
    finally:  # pragma: no cover - network cleanup
        await smtp.quit()
