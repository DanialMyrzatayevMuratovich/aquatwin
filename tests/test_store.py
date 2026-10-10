import sys
import types

import pytest

from aquatwin import store


@pytest.fixture
def fake_db(monkeypatch):
    """A stand-in for psycopg: one table in a dict, and a switch to make it fail."""
    state = {"rows": {}, "fail": False, "connects": 0}

    class Error(Exception):
        pass

    class Cursor:
        description = None

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params):
            if state["fail"]:
                raise Error("connection lost")
            if sql.startswith("select"):
                self.description, self._row = ("lang",), state["rows"].get(params[0])
            else:
                self.description, state["rows"][params[0]] = None, params[1]

        def fetchone(self):
            return (self._row,) if self._row else None

    class Connection:
        closed = False

        def cursor(self):
            return Cursor()

        def close(self):
            self.closed = True

    def connect(url, **kwargs):
        state["connects"] += 1
        if state["fail"]:
            raise Error("could not connect")
        return Connection()

    monkeypatch.setitem(sys.modules, "psycopg", types.SimpleNamespace(Error=Error, connect=connect))
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(store, "_conn", None)
    monkeypatch.setattr(store, "_down_until", 0.0)
    return state


def test_store_is_off_without_database_url():
    assert not store.enabled()
    store.set_lang(1, "kk")           # must not need the driver or raise
    assert store.get_lang(1) is None


def test_language_roundtrip_on_one_connection(fake_db):
    assert store.get_lang(7) is None
    store.set_lang(7, "kk")
    store.set_lang(7, "en")
    assert store.get_lang(7) == "en" and fake_db["connects"] == 1


def test_database_failure_is_swallowed_and_the_store_rests(fake_db):
    store.set_lang(7, "kk")
    fake_db["fail"] = True
    assert store.get_lang(7) is None              # no exception reaches the bot
    attempts = fake_db["connects"]
    assert store.get_lang(7) is None and fake_db["connects"] == attempts  # resting: the database is not asked again
