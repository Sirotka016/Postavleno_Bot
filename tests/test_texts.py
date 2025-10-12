from datetime import UTC, datetime

from postavleno_bot.services.accounts import AccountProfile
from postavleno_bot.ui.texts import help_message, profile_header


def build_profile(**overrides: object) -> AccountProfile:
    base = dict(
        display_login="Demo",
        username="demo",
        password_hash="hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        company_name="Demo LLC",
        email="user@example.com",
        wb_api="TOKEN1234567890",
        email_verified=True,
        email_pending_hash=None,
        email_pending_expires_at=None,
    )
    base.update(overrides)
    return AccountProfile.from_dict(base)


def test_profile_header_includes_status_icons() -> None:
    profile = build_profile()
    text = profile_header(profile)
    assert "👤 Профиль: Demo" in text
    assert "Компания: Demo LLC" in text
    assert "Почта: user@example.com (подтверждена ✅)" in text
    assert "WB API" in text
    assert "Дата регистрации: 01.01.2024" in text


def test_help_message_switches_for_authorization() -> None:
    unauth = help_message("Гость", authorized=False)
    auth = help_message("Demo", authorized=True)

    expected_unauth = "\n".join(
        [
            "Привет, Гость! ✨",
            "Меня зовут Postavleno_Bot.",
            "",
            "Как начать:",
            "1) Пройдите авторизацию/регистрацию, чтобы продолжить.",
            "2) Нажмите «Профиль» и заполните:",
            "   — «Компания» — укажите название (можно изменить позже).",
            "   — «Почта» — привяжите и подтвердите email (на него придёт код).",
            "   — «WB API» — добавьте ключ из кабинета WB (Доступ к API).",
            "3) Вернитесь на главное окно и выберите нужную выгрузку.",
            "4) «Обновить» — перезапрос данных и актуализация статусов.",
            "5) «Выйти» — завершить сессию.",
        ]
    )
    expected_auth = "\n".join(
        [
            "Привет, Demo! ✨",
            "Меня зовут Postavleno_Bot.",
            "",
            "Как начать:",
            "1) Откройте «Профиль» и при необходимости дополните данные:",
            "   — «Компания» — укажите/измените название.",
            "   — «Почта» — привяжите и подтвердите email (на него придёт код).",
            "   — «WB API» — добавьте или обновите ключ из кабинета WB (Доступ к API).",
            "2) Вернитесь на главное окно и выберите нужную выгрузку.",
            "3) «Обновить» — перезапрос данных и актуализация статусов.",
            "4) «Выйти» — завершить сессию.",
        ]
    )

    assert unauth == expected_unauth
    assert auth == expected_auth
