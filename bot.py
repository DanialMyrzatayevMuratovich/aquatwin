"""AquaTwin Telegram bot.

Run locally:  export TELEGRAM_TOKEN=...   (from @BotFather)
              python bot.py              # add --replay to demonstrate without internet

On Render the bot switches to webhook mode by itself: Render sets RENDER_EXTERNAL_URL
for web services, and an incoming Telegram message wakes a sleeping free instance.
"""
import asyncio
import datetime as dt
import hashlib
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from telegram import KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, TypeHandler, filters

from aquatwin import advice, config, data, drought, nearest_region, store

log = logging.getLogger("aquatwin.bot")

REPLAY = "--replay" in sys.argv
MAX_DISTANCE_KM = 150
CACHE_TTL_S = 3 * 3600
LANG_WAIT_S = 0.5
ASSESSMENT_WAIT_S = 25
MAX_INFLIGHT = 4
REGIONS = {r["id"]: r for r in config.REGIONS}
LANGS = {"Русский": "ru", "Қазақша": "kk", "English": "en"}
_cache: dict[tuple, tuple[float, drought.Assessment]] = {}
_inflight: dict[tuple, asyncio.Task] = {}
# Optional database I/O cannot use up the threads needed for weather calculations.
_language_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bot-language")

TEXT = {
    "start": {
        "ru": "Здравствуйте! Я AquaTwin 💧\nПоказываю районные индикаторы засухи и рекомендации для планирования воды.\n\n📍 Отправьте геолокацию на юге Казахстана\n/district maktaaral — текущий прогноз моделей\n/replay 2021-05-07 maktaaral — исторический пример\n\nВыберите язык ниже.",
        "kk": "Сәлеметсіз бе! Мен AquaTwin 💧\nАудан деңгейіндегі құрғақшылық көрсеткіштері мен суды жоспарлау ұсыныстарын көрсетемін.\n\n📍 Қазақстанның оңтүстігіндегі геолокацияны жіберіңіз\n/district maktaaral — модельдердің қазіргі болжамы\n/replay 2021-05-07 maktaaral — тарихи мысал\n\nТөменнен тілді таңдаңыз.",
        "en": "Hi! I'm AquaTwin 💧\nExplore district-level drought indicators and suggested actions for water planning.\n\n📍 Send a location in southern Kazakhstan\n/district maktaaral — current model outlook\n/replay 2021-05-07 maktaaral — historical example\n\nChoose your language below.",
    },
    "button": {"ru": "📍 Отправить геолокацию", "kk": "📍 Геолокация жіберу", "en": "📍 Send location"},
    "far": {
        "ru": "Пока работаем только в пилотных районах Туркестанской и Кызылординской областей.",
        "kk": "Әзірге тек Түркістан және Қызылорда облыстарының пилоттық аудандарында жұмыс істейміз.",
        "en": "We currently cover pilot districts of Turkistan and Kyzylorda regions only.",
    },
    "wait": {"ru": "Считаю прогноз…", "kk": "Болжамды есептеп жатырмын…", "en": "Computing forecast…"},
    "slow": {
        "ru": "Поставщик погоды отвечает медленно. Расчёт продолжается; повторите запрос чуть позже. Для исторического примера: /replay 2021-05-07 maktaaral",
        "kk": "Ауа райы дерегін жеткізуші баяу жауап беріп жатыр. Есептеу жалғасады; сәлден соң қайта сұраңыз. Тарихи мысал: /replay 2021-05-07 maktaaral",
        "en": "The weather provider is responding slowly. The calculation is still running; please try again shortly. For a historical example: /replay 2021-05-07 maktaaral",
    },
    "busy": {
        "ru": "Сейчас считаю несколько районов. Попробуйте чуть позже; /start и /help доступны.",
        "kk": "Қазір бірнеше аудан есептеліп жатыр. Сәлден соң қайталаңыз; /start және /help қолжетімді.",
        "en": "Several district calculations are running. Please try shortly; /start and /help are available.",
    },
    "error": {
        "ru": "Не получилось посчитать прогноз. Попробуйте ещё раз через минуту.",
        "kk": "Болжамды есептеу мүмкін болмады. Бір минуттан кейін қайталап көріңіз.",
        "en": "Could not compute the forecast. Please try again in a minute.",
    },
    "help": {
        "ru": ("Что я умею:\n📍 геолокация — риск засухи для ближайшего пилотного района\n"
               "/district <район> — то же без геолокации\n/replay <ГГГГ-ММ-ДД> <район> — что было в прошлом\n\n"
               "Риск — это доля сценариев прогноза ECMWF с засушливым периодом. "
               "Точность — по районам, а не по отдельным полям."),
        "kk": ("Мен не істей аламын:\n📍 геолокация — ең жақын пилоттық аудан үшін құрғақшылық қаупі\n"
               "/district <аудан> — геолокациясыз\n/replay <ЖЖЖЖ-АА-КК> <аудан> — өткен кезеңде не болды\n\n"
               "Қауіп — ECMWF болжамының құрғақ кезең көрсеткен сценарийлерінің үлесі. "
               "Дәлдік — жеке егістік емес, аудан деңгейінде."),
        "en": ("What I can do:\n📍 location — drought risk for the nearest pilot district\n"
               "/district <id> — the same without a location\n/replay <YYYY-MM-DD> <id> — what happened in the past\n\n"
               "Risk is the share of ECMWF forecast scenarios with a dry spell. "
               "Accuracy is district-level, not field-level."),
    },
    "replay_usage": {
        "ru": "Пример: /replay 2021-06-15 kyzylorda\nДаты: с 1991-04-01 по 2025-11-15.",
        "kk": "Мысал: /replay 2021-06-15 kyzylorda\nКүндер: 1991-04-01 – 2025-11-15.",
        "en": "Example: /replay 2021-06-15 kyzylorda\nDates: 1991-04-01 to 2025-11-15.",
    },
}


def lang_of(update: object, context: ContextTypes.DEFAULT_TYPE) -> str:
    """The chosen language; before a choice (or after a restart) the language of the user's Telegram app."""
    chosen = (context.user_data or {}).get("lang")
    if chosen:
        return chosen
    user = update.effective_user if isinstance(update, Update) else None
    code = user.language_code if user is not None else None
    return code[:2] if isinstance(code, str) and code[:2] in LANGS.values() else "ru"


def keyboard(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[KeyboardButton(TEXT["button"][lang], request_location=True)], list(LANGS)],
                               resize_keyboard=True)


def assess_region(region: dict, replay_date: str | None = None) -> drought.Assessment:
    """Assessment for a district; live results are reused for CACHE_TTL_S."""
    mode = "replay" if REPLAY or replay_date else "live"
    key = (region["id"], mode, replay_date)
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    a = drought.assess(data.load_region(region, mode=mode, replay_date=replay_date))
    if a.source == "live" or mode == "replay":  # a fallback result is retried on the next request
        _cache[key] = (time.monotonic(), a)
    return a


async def reply_assessment(update: Update, context: ContextTypes.DEFAULT_TYPE, region: dict,
                           replay_date: str | None = None) -> None:
    lang = lang_of(update, context)
    key = (region["id"], REPLAY, replay_date)
    task = _inflight.get(key)
    if task is None:
        if len(_inflight) >= MAX_INFLIGHT:
            await update.effective_message.reply_text(TEXT["busy"][lang])
            return
        task = asyncio.create_task(asyncio.to_thread(assess_region, region, replay_date))
        _inflight[key] = task

        def finished(done):
            if _inflight.get(key) is done:
                _inflight.pop(key, None)
            if not done.cancelled():
                done.exception()  # retrieve errors even if the caller's wait has ended
        task.add_done_callback(finished)
    try:
        a = await asyncio.wait_for(asyncio.shield(task), timeout=ASSESSMENT_WAIT_S)
    except asyncio.TimeoutError:
        await update.effective_message.reply_text(TEXT["slow"][lang])
        return
    await update.effective_message.reply_text(advice.message(a, region, lang), parse_mode="Markdown")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update, context)
    await update.effective_message.reply_text(TEXT["start"][lang], reply_markup=keyboard(lang))


async def help_(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(TEXT["help"][lang_of(update, context)])


async def load_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs before every handler: after a restart, bring back the language the user chose earlier."""
    data_ = context.user_data
    if data_ is None or "lang" in data_ or data_.get("lang_checked") or update.effective_user is None:
        return
    data_["lang_checked"] = True
    try:
        future = asyncio.get_running_loop().run_in_executor(_language_pool, store.get_lang, update.effective_user.id)
        lang = await asyncio.wait_for(future, timeout=LANG_WAIT_S)
    except asyncio.TimeoutError:
        return  # use Telegram's language; optional storage must not hold up /start
    if lang in LANGS.values() and "lang" not in data_:
        data_["lang"] = lang


async def set_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["lang"] = LANGS[update.effective_message.text]
    await start(update, context)
    if update.effective_user is not None:
        try:
            future = asyncio.get_running_loop().run_in_executor(_language_pool, store.set_lang,
                                                               update.effective_user.id, context.user_data["lang"])
            await asyncio.wait_for(future, timeout=LANG_WAIT_S)
        except asyncio.TimeoutError:
            pass  # the choice is already active in memory


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update, context)
    loc = update.effective_message.location
    region, km = nearest_region(loc.latitude, loc.longitude)
    if km > MAX_DISTANCE_KM:
        await update.effective_message.reply_text(TEXT["far"][lang])
        return
    await update.effective_message.reply_text(TEXT["wait"][lang])
    await reply_assessment(update, context, region)


async def by_district(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/district maktaaral — check a district without sending a location."""
    arg = (context.args or [""])[0].lower()
    if arg not in REGIONS:
        await update.effective_message.reply_text("/district " + " | ".join(REGIONS))
        return
    await update.effective_message.reply_text(TEXT["wait"][lang_of(update, context)])
    await reply_assessment(update, context, REGIONS[arg])


async def replay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/replay 2021-06-15 kyzylorda — real history for a past date (not a forecast)."""
    args = [a.lower() for a in context.args or []]
    region = next((REGIONS[a] for a in args if a in REGIONS), None)
    date = next((a for a in args if a not in REGIONS), None)
    try:
        dt.date.fromisoformat(date or "")
        if region is None:
            raise ValueError("district is missing")
        await reply_assessment(update, context, region, replay_date=date)
    except ValueError:  # bad date, unknown district, or a date outside the baseline period
        await update.effective_message.reply_text(TEXT["replay_usage"][lang_of(update, context)])


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("handler failed", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(TEXT["error"][lang_of(update, context)])


def build(token: str) -> Application:
    # Independent commands: a weather request must not queue every user's /start.
    app = Application.builder().token(token).concurrent_updates(8).build()
    new_message = ~filters.UpdateType.EDITED  # live-location updates arrive as edits; answer only once
    app.add_handler(TypeHandler(Update, load_lang), group=-1)
    app.add_handler(CommandHandler("start", start, filters=new_message))
    app.add_handler(CommandHandler("help", help_, filters=new_message))
    app.add_handler(CommandHandler("district", by_district, filters=new_message))
    app.add_handler(CommandHandler("replay", replay, filters=new_message))
    app.add_handler(MessageHandler(filters.Regex(f"^({'|'.join(LANGS)})$") & new_message, set_lang))
    app.add_handler(MessageHandler(filters.LOCATION & new_message, on_location))
    app.add_error_handler(on_error)
    return app


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines contain the bot token
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        sys.exit("Set TELEGRAM_TOKEN (get one from @BotFather).")
    app = build(token)
    url = None if "--polling" in sys.argv else os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        secret = hashlib.sha256(token.encode()).hexdigest()
        app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", "10000")), url_path=secret[:32],
                        webhook_url=f"{url.rstrip('/')}/{secret[:32]}", secret_token=secret[32:])
    else:
        app.run_polling()


if __name__ == "__main__":
    main()
