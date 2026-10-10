import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Update

import bot


@pytest.fixture(autouse=True)
def replay_mode(monkeypatch):
    """Handlers are exercised on the replay path, which needs no network."""
    monkeypatch.setattr(bot, "REPLAY", True)
    monkeypatch.setattr(bot, "_cache", {})


def call(handler, text=None, lat=None, lon=None, args=None, user_data=None, app_lang=None):
    update = MagicMock(spec=Update)
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.text = text
    update.effective_user.language_code = app_lang
    if lat is not None:
        update.effective_message.location.latitude = lat
        update.effective_message.location.longitude = lon
    context = MagicMock()
    context.user_data = {} if user_data is None else user_data
    context.args = args
    asyncio.run(handler(update, context))
    return [c.args[0] for c in update.effective_message.reply_text.call_args_list], \
           [c.kwargs for c in update.effective_message.reply_text.call_args_list]


def test_start_shows_location_button_and_languages():
    texts, kwargs = call(bot.start)
    rows = kwargs[0]["reply_markup"].keyboard
    assert texts[0] == bot.TEXT["start"]["ru"]
    assert rows[0][0].request_location and [b.text for b in rows[1]] == ["Русский", "Қазақша", "English"]


@pytest.mark.parametrize("label, lang", [("Қазақша", "kk"), ("English", "en"), ("Русский", "ru")])
def test_language_switch(label, lang):
    user_data = {}
    texts, _ = call(bot.set_lang, text=label, user_data=user_data)
    assert user_data["lang"] == lang and texts[0] == bot.TEXT["start"][lang]


@pytest.mark.parametrize("app_lang, expected", [("kk", "kk"), ("en-US", "en"), ("ru", "ru"), ("de", "ru"), (None, "ru")])
def test_language_defaults_to_the_telegram_app_language(app_lang, expected):
    """After a restart the bot has no stored choice, so it follows the user's Telegram language."""
    texts, _ = call(bot.start, app_lang=app_lang)
    assert texts[0] == bot.TEXT["start"][expected]
    texts, _ = call(bot.start, app_lang=app_lang, user_data={"lang": "en"})
    assert texts[0] == bot.TEXT["start"]["en"]  # an explicit choice wins


def test_location_in_pilot_district_gets_an_assessment():
    texts, kwargs = call(bot.on_location, lat=40.67, lon=68.55, user_data={"lang": "en"})
    assert texts[0] == bot.TEXT["wait"]["en"]
    assert "District: Maktaaral" in texts[1] and "not a forecast" in texts[1]
    assert kwargs[1]["parse_mode"] == "Markdown"


def test_location_far_away_is_declined():
    texts, _ = call(bot.on_location, lat=43.24, lon=76.95, user_data={"lang": "en"})  # Almaty
    assert texts == [bot.TEXT["far"]["en"]]


def test_district_command():
    texts, _ = call(bot.by_district, args=["Kyzylorda"], user_data={"lang": "kk"})
    assert "Аудан: Қызылорда" in texts[0]
    texts, _ = call(bot.by_district, args=[])
    assert texts[0].startswith("/district maktaaral | ")


def test_replay_command():
    texts, _ = call(bot.replay, args=["2021-06-15", "kyzylorda"], user_data={"lang": "ru"})
    assert "Район: Кызылорда" in texts[0] and "15.06.2021" in texts[0]
    for bad in (["kyzylorda"], ["2021-06-15"], ["yesterday", "kyzylorda"], ["2030-01-01", "kyzylorda"], []):
        texts, _ = call(bot.replay, args=bad, user_data={"lang": "ru"})
        assert texts == [bot.TEXT["replay_usage"]["ru"]]


def test_assessment_is_cached(monkeypatch):
    calls = []
    original = bot.data.load_region
    monkeypatch.setattr(bot.data, "load_region", lambda *a, **k: calls.append(1) or original(*a, **k))
    for _ in range(3):
        call(bot.by_district, args=["sairam"])
    assert len(calls) == 1


def test_error_handler_answers_the_user():
    update = MagicMock(spec=Update)
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    context.user_data, context.error = {"lang": "en"}, RuntimeError("boom")
    asyncio.run(bot.on_error(update, context))
    update.effective_message.reply_text.assert_awaited_once_with(bot.TEXT["error"]["en"])


def test_language_is_restored_from_the_store_after_a_restart(monkeypatch):
    asked = []
    monkeypatch.setattr(bot.store, "get_lang", lambda user_id: asked.append(user_id) or "kk")
    update, context = MagicMock(spec=Update), MagicMock()
    update.effective_user.id, context.user_data = 42, {}
    asyncio.run(bot.load_lang(update, context))
    asyncio.run(bot.load_lang(update, context))  # the store is asked once per user per process
    assert context.user_data["lang"] == "kk" and asked == [42]


def test_unknown_user_keeps_the_telegram_language(monkeypatch):
    monkeypatch.setattr(bot.store, "get_lang", lambda user_id: None)
    update, context = MagicMock(spec=Update), MagicMock()
    update.effective_user.id, context.user_data = 42, {}
    asyncio.run(bot.load_lang(update, context))
    assert "lang" not in context.user_data


def test_language_choice_is_saved(monkeypatch):
    saved = []
    monkeypatch.setattr(bot.store, "set_lang", lambda user_id, lang: saved.append((user_id, lang)))
    update = MagicMock(spec=Update)
    update.effective_message.reply_text = AsyncMock()
    update.effective_message.text, update.effective_user.id = "English", 42
    context = MagicMock()
    context.user_data = {}
    asyncio.run(bot.set_lang(update, context))
    assert saved == [(42, "en")]


def test_application_wiring():
    app = bot.build("123456:TEST-TOKEN")
    assert len(app.handlers[0]) == 6 and len(app.handlers[-1]) == 1 and app.error_handlers
