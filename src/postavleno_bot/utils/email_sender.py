"""Helpers for sending verification emails."""

from __future__ import annotations

from email.headerregistry import Address
from email.message import EmailMessage

from aiosmtplib import SMTP, SMTPException


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
    """Send an email via SMTP with the proper TLS workflow."""

    message = EmailMessage()
    message["From"] = str(Address(display_name=sender_name, addr_spec=username))
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    if port == 465:
        smtp = SMTP(hostname=host, port=port, use_tls=True, timeout=timeout)
        await smtp.connect()
    else:
        smtp = SMTP(hostname=host, port=port, start_tls=False, timeout=timeout)
        await smtp.connect()
        await smtp.starttls()

    try:
        await smtp.login(username, password)
        await smtp.send_message(message)
    finally:  # pragma: no cover - network cleanup
        try:
            await smtp.quit()
        except SMTPException:
            pass
