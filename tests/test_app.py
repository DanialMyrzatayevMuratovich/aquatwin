"""The dashboard script itself, run headlessly. Without network it shows the replay fallback."""
import pathlib
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

from aquatwin import config, data

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
HEADER = "Every drop. A clearer decision."


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("AQUATWIN_DEFAULT_MODE", raising=False)
    return AppTest.from_file(APP, default_timeout=120)


def test_dashboard_renders_without_network(app):
    app.run()
    assert not app.exception
    assert app.radio[0].value == "Live forecast"
    assert any(HEADER in h.value for h in app.title)
    assert any("replay of real history" in w.value for w in app.warning)  # the offline fallback is labelled
    assert len(app.metric) == 4 and len(app.dataframe[0].value) == 8


def test_pitch_starts_in_labelled_replay_without_api_requests(app, monkeypatch):
    monkeypatch.setenv("AQUATWIN_DEFAULT_MODE", "replay")
    request = Mock(side_effect=AssertionError("Pitch startup must not fetch weather data"))
    monkeypatch.setattr(data.requests, "get", request)
    app.run()
    assert not app.exception
    assert app.radio[0].value == "Replay of the past"
    assert app.date_input[0].value.isoformat() == config.REPLAY_DEFAULT_DATE
    assert any("not a forecast" in info.value for info in app.info)
    assert len(app.metric) == 4 and len(app.dataframe[0].value) == 8
    request.assert_not_called()


def test_login_is_required_when_credentials_are_configured(app, monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", "admin@example.org")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "correct horse")
    app.run()
    assert not app.exception and not app.title and not app.metric  # nothing but the sign-in view

    app.text_input[0].set_value("admin@example.org")
    app.text_input[1].set_value("wrong")
    app.button[0].click().run()
    assert [e.value for e in app.error] == ["Wrong login or password."] and not app.metric

    app.text_input[0].set_value(" Admin@Example.org ")  # the login ignores case and spaces
    app.text_input[1].set_value("correct horse")
    app.button[0].click().run()
    assert not app.exception and any(HEADER in h.value for h in app.title) and len(app.metric) == 4


def test_district_and_language_change_the_message_and_replay_has_no_probability(app, monkeypatch):
    monkeypatch.setenv("AQUATWIN_DEFAULT_MODE", "replay")
    app.run()
    app.sidebar.selectbox[0].set_value("kk").run()
    app.selectbox(key="selected_district").set_value("kyzylorda").run()
    assert not app.exception
    content = "\n".join(m.value for m in app.markdown)
    assert "Аудан: Қызылорда" in content
    assert "Telegram message preview · KK" in content
    assert "Actual dry-spell onset" in content
    assert "<small>% of scenarios</small>" not in content
