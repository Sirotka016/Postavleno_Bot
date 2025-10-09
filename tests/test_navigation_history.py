from __future__ import annotations

from postavleno_bot.state.session import ChatSession, ScreenState, nav_back, nav_push


def test_history_back_goes_to_prev_page() -> None:
    session = ChatSession()
    nav_push(session, ScreenState(name="WB_PAGE", params={"page": 2}))
    nav_push(session, ScreenState(name="WB_PAGE", params={"page": 3}))

    previous = nav_back(session)

    assert previous is not None
    assert previous.name == "WB_PAGE"
    assert previous.params["page"] == 2
    assert len(session.history) == 1


def test_history_back_from_upload_returns_to_local_open() -> None:
    session = ChatSession()
    nav_push(session, ScreenState(name="LOCAL_OPEN", params={}))
    nav_push(session, ScreenState(name="LOCAL_UPLOAD", params={}))

    previous = nav_back(session)

    assert previous is not None
    assert previous.name == "LOCAL_OPEN"
    assert len(session.history) == 1
