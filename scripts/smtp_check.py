"""Simple SMTP connectivity check script."""

from __future__ import annotations

import asyncio
import os
from email.message import EmailMessage

from aiosmtplib import SMTP, SMTPException


async def main() -> None:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    recipient = os.getenv("SMTP_TEST_TO", user)

    if not user or not password:
        raise SystemExit("SMTP_USER and SMTP_PASSWORD environment variables must be set")

    message = EmailMessage()
    message["From"] = f"Postavleno_Bot <{user}>"
    message["To"] = recipient
    message["Subject"] = "Тест SMTP — Postavleno_Bot"
    message.set_content("Это тестовое письмо. Если вы его видите — SMTP настроен 👍")

    smtp = SMTP(hostname=host, port=port, start_tls=True, timeout=20)
    await smtp.connect()
    try:
        await smtp.login(user, password)
        await smtp.send_message(message)
    finally:
        try:
            await smtp.quit()
        except SMTPException:
            pass

    print("OK: письмо отправлено")


if __name__ == "__main__":
    asyncio.run(main())
