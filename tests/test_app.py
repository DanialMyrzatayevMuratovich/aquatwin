"""The dashboard script itself, run headlessly. Without network it shows the replay fallback."""
import pathlib

import pytest
from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
HEADER = "Turkistan & Kyzylorda pilot"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.delenv("DASHBOARD_USER", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    return AppTest.from_file(APP, default_timeout=120)


def test_dashboard_renders_without_network(app):
    app.run()
    assert not app.exception
    assert any(HEADER in h.value for h in app.header)
    assert any("replay of real history" in w.value for w in app.warning)  # the offline fallback is labelled
    assert len(app.metric) == 4 and len(app.dataframe[0].value) == 8


def test_login_is_required_when_credentials_are_configured(app, monkeypatch):
    monkeypatch.setenv("DASHBOARD_USER", "admin@example.org")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "correct horse")
    app.run()
    assert not app.exception and not app.header and not app.metric  # nothing but the form

    app.text_input[0].set_value("admin@example.org")
    app.text_input[1].set_value("wrong")
    app.button[0].click().run()
    assert [e.value for e in app.error] == ["Wrong login or password."] and not app.header

    app.text_input[0].set_value(" Admin@Example.org ")  # the login ignores case and spaces
    app.text_input[1].set_value("correct horse")
    app.button[0].click().run()
    assert not app.exception and any(HEADER in h.value for h in app.header) and len(app.metric) == 4
