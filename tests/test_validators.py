from postavleno_bot.domain.validators import validate_login, validate_ms, validate_wb


def test_validate_login() -> None:
    assert validate_login("user.name")
    assert not validate_login("ab")
    assert not validate_login("user name")


def test_validate_wb_accepts_jwt_like() -> None:
    token = "a" * 64
    assert validate_wb(token)
    assert validate_wb("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
    assert not validate_wb("short")


def test_validate_ms_accepts_extended_charset() -> None:
    token = "A" * 32
    assert validate_ms(token)
    assert not validate_ms("токен")
