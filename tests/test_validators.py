from postavleno_bot.domain.validators import (
    validate_company_name,
    validate_email,
    validate_login,
    validate_wb,
)


def test_validate_login() -> None:
    assert validate_login("user.name")
    assert not validate_login("ab")
    assert not validate_login("user name")


def test_validate_wb_accepts_jwt_like() -> None:
    token = "a" * 64
    assert validate_wb(token)
    assert validate_wb("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert validate_wb(".".join(["a" * 16, "b" * 16, "c" * 16]))
    assert not validate_wb("short")
    assert not validate_wb("a" * 513)


def test_validate_email() -> None:
    assert validate_email("user@example.com")
    assert validate_email("user.name+tag@sub.example.co")
    assert not validate_email("user@example")
    assert not validate_email("user example@example.com")


def test_validate_company_name() -> None:
    assert validate_company_name("OOO Ромашка")
    assert validate_company_name("My Co")
    assert validate_company_name("A")
    assert validate_company_name("B" * 70)
    assert not validate_company_name(" ")
    assert not validate_company_name("")
    assert not validate_company_name("B" * 71)
    assert not validate_company_name("Name\nWithBreak")
