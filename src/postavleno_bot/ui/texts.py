"""Collection of reusable text builders for bot messages."""

from __future__ import annotations

from ..services.accounts import AccountProfile
from ..utils.formatting import format_date_ru, mask_token
from ..help.steps import profile_step_lines


def profile_header(profile: AccountProfile) -> str:
    company_name = (profile.company_name or "").strip()
    company_icon = "✅" if company_name else "❌"
    company_value = company_name or "—"

    email_value = "—"
    email_icon = "❌"
    if profile.email:
        email = profile.email
        if profile.email_verified:
            email_icon = "✅"
            email_value = f"{email} (подтверждена ✅)"
        else:
            email_icon = "❌"
            email_value = f"{email} (нужно подтвердить ❌)"
    elif profile.email_verified:
        # Defensive branch: verified flag without email should not happen.
        email_icon = "❌"
        email_value = "—"

    wb_token = (profile.wb_api or "").strip()
    wb_icon = "✅" if wb_token else "❌"
    wb_value = mask_token(wb_token)

    created_at = format_date_ru(profile.created_at)

    return (
        f"👤 Профиль: {profile.display_login}\n\n"
        f"{company_icon} Компания: {company_value}\n"
        f"{email_icon} Почта: {email_value}\n"
        f"{wb_icon} WB API: {wb_value}\n\n"
        f"Дата регистрации: {created_at}"
    )


def company_prompt_text() -> str:
    return (
        "Введите название вашей компании. Это имя будет отображаться в профиле. "
        "Можно изменить позже."
    )


def company_rename_prompt_text() -> str:
    return "Отправьте новое название компании."


def company_menu_text(company_name: str) -> str:
    return f"📁 Компания\n\nТекущее название: {company_name}"


def company_delete_confirm_text() -> str:
    return "Точно удалить? Действие необратимо."


def email_prompt_text() -> str:
    return (
        "Укажите ваш email. Мы отправим код подтверждения с адреса "
        "NeAniiime@gmail.com."
    )


def email_menu_text(email: str, verified: bool) -> str:
    status = "подтверждена ✅" if verified else "нужно подтвердить ❌"
    return f"✉️ Почта\n\nТекущий адрес: {email}\nСтатус: {status}"


def email_code_prompt(email: str) -> str:
    return (
        f"Мы отправили код на {email}. Введите его одним сообщением.\n"
        "Код действует 10 минут."
    )


def email_unlink_confirm_text() -> str:
    return "Отвязать почту? Точно удалить? Действие необратимо."


def wb_prompt_text() -> str:
    return (
        "Отправьте ключ WB API (кабинет WB → Доступ к API). Ключ хранится у нас в "
        "зашифрованном виде."
    )


def wb_menu_text(masked: str) -> str:
    return f"🔑 WB API\n\nТекущий ключ: {masked}"


def wb_delete_confirm_text() -> str:
    return "Точно удалить ключ WB API? Действие необратимо."


def help_message(tg_name: str, *, authorized: bool) -> str:
    header = [
        f"Привет, {tg_name}! ✨",
        "Меня зовут Postavleno_Bot.",
        "",
        "Как начать:",
    ]
    if authorized:
        body = [
            "1) Откройте «Профиль» и при необходимости дополните данные:",
            *profile_step_lines(authorized=True),
            "2) Вернитесь на главное окно и выберите нужную выгрузку.",
            "3) «Обновить» — перезапрос данных и актуализация статусов.",
            "4) «Выйти» — завершить сессию.",
        ]
    else:
        body = [
            "1) Пройдите авторизацию/регистрацию, чтобы продолжить.",
            "2) Нажмите «Профиль» и заполните:",
            *profile_step_lines(authorized=False),
            "3) Вернитесь на главное окно и выберите нужную выгрузку.",
            "4) «Обновить» — перезапрос данных и актуализация статусов.",
            "5) «Выйти» — завершить сессию.",
        ]

    return "\n".join([*header, *body])


__all__ = [
    "company_delete_confirm_text",
    "company_menu_text",
    "company_rename_prompt_text",
    "company_prompt_text",
    "email_code_prompt",
    "email_menu_text",
    "email_prompt_text",
    "email_unlink_confirm_text",
    "help_message",
    "profile_header",
    "wb_delete_confirm_text",
    "wb_menu_text",
    "wb_prompt_text",
]
