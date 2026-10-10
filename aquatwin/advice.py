"""Turns a drought assessment into a short, actionable message (EN / RU / KK)."""
from __future__ import annotations

from . import config
from .drought import Assessment

EMOJI = {"low": "🟢", "moderate": "🟡", "high": "🔴", "ongoing": "🟤"}

TITLE = {
    "en": {"low": "Low drought risk", "moderate": "Moderate drought risk",
           "high": "HIGH risk: flash drought expected", "ongoing": "Drought is already under way"},
    "ru": {"low": "Низкий риск засухи", "moderate": "Умеренный риск засухи",
           "high": "ВЫСОКИЙ риск: ожидается внезапная засуха", "ongoing": "Засуха уже началась"},
    "kk": {"low": "Құрғақшылық қаупі төмен", "moderate": "Құрғақшылық қаупі орташа",
           "high": "ЖОҒАРЫ қауіп: кенеттен құрғақшылық күтілуде", "ongoing": "Құрғақшылық басталып кетті"},
}

# Not yet reviewed by an agronomist.
ACTIONS = {
    "en": {
        "low": ["Keep your normal irrigation schedule.", "Check again next week — the forecast updates daily."],
        "moderate": ["Plan the next irrigation a few days earlier than usual.",
                     "Mulch or loosen the topsoil to keep moisture in.",
                     "Agree your water turn with the water users' association now."],
        "high": ["Irrigate priority fields BEFORE the dry spell starts.",
                 "Book your water turn with the water users' association today.",
                 "If you have not sown yet, consider a drought-tolerant crop or variety.",
                 "Avoid fertilizing just before the dry spell."],
        "ongoing": ["Concentrate water on the most valuable fields.",
                    "Irrigate early morning or evening to cut evaporation.",
                    "Contact the akimat / insurer — document crop condition with photos."],
    },
    "ru": {
        "low": ["Поливайте по обычному графику.", "Проверьте снова через неделю — прогноз обновляется ежедневно."],
        "moderate": ["Запланируйте следующий полив на несколько дней раньше обычного.",
                     "Замульчируйте или разрыхлите верхний слой почвы, чтобы сохранить влагу.",
                     "Уже сейчас согласуйте очередь на воду с водопользователями."],
        "high": ["Полейте приоритетные поля ДО начала засухи.",
                 "Сегодня же забронируйте очередь на воду у водопользователей.",
                 "Если ещё не посеяли — рассмотрите засухоустойчивую культуру или сорт.",
                 "Не вносите удобрения прямо перед засухой."],
        "ongoing": ["Направьте воду на самые ценные поля.",
                    "Поливайте рано утром или вечером, чтобы меньше воды испарялось.",
                    "Обратитесь в акимат или к страховщику, сфотографируйте состояние посевов."],
    },
    "kk": {
        "low": ["Әдеттегі кестемен суара беріңіз.", "Бір аптадан кейін қайта тексеріңіз — болжам күн сайын жаңарады."],
        "moderate": ["Келесі суаруды әдеттегіден бірнеше күн ертерек жоспарлаңыз.",
                     "Ылғалды сақтау үшін топырақтың үстіңгі қабатын мульчалаңыз немесе қопсытыңыз.",
                     "Су пайдаланушылар бірлестігімен су кезегін қазірден келісіп алыңыз."],
        "high": ["Басым егістіктерді құрғақшылық басталмай ТҰРЫП суарыңыз.",
                 "Су пайдаланушылар бірлестігінен су кезегін бүгін брондаңыз.",
                 "Әлі екпеген болсаңыз, құрғақшылыққа төзімді дақылды немесе сортты қарастырыңыз.",
                 "Құрғақшылық алдында тыңайтқыш енгізбеңіз."],
        "ongoing": ["Суды ең құнды егістіктерге бағыттаңыз.",
                    "Буланудың азаюы үшін таңертең ерте немесе кешке суарыңыз.",
                    "Әкімдікке немесе сақтандырушыға хабарласып, егіннің жағдайын суретке түсіріңіз."],
    },
}

# Kazakh labels below are drafts and need a native speaker's review.
LABELS = {
    "en": {
        "district": "District",
        "deficit": "14-day water deficit (evaporation − rain): {d} mm, normal {n} mm",
        "surplus": "14-day water surplus (rain − evaporation): {d} mm",
        "dryness": "Dryness: percentile {p} (compared with the 1991–2020 norm)",
        "prob": "Chance of a dry spell in the next 6 weeks: {p}% ({k} of {n} ECMWF scenarios)",
        "onset": "Expected onset: {date} (in {d} days)",
        "onset_actual": "Dry spell actually started: {date}",
        "ai": "ECMWF AIFS AI model, 2 weeks: {k} of {n} scenarios",
        "todo": "What to do",
        "offseason": "Outside the irrigation season ({season}). Monitoring continues.",
        "live": "📡 Live data: observations through {date}, ECMWF forecast for the next 6 weeks",
        "snapshot": "Data as of {date}",
        "replay": "⏪ Replay of the past: actual data for {date}, not a forecast",
    },
    "ru": {
        "district": "Район",
        "deficit": "Дефицит влаги за 14 дней (испарение − осадки): {d} мм, норма {n} мм",
        "surplus": "Избыток влаги за 14 дней (осадки − испарение): {d} мм",
        "dryness": "Сухость: {p}-й перцентиль (сравнение с нормой 1991–2020)",
        "prob": "Вероятность засушливого периода в ближайшие 6 недель: {p} % ({k} из {n} {scen} ECMWF)",
        "onset": "Ожидаемое начало: {date} (через {d} дн.)",
        "onset_actual": "Засушливый период по факту начался: {date}",
        "ai": "AI-модель ECMWF AIFS, 2 недели: {k} из {n} {scen}",
        "todo": "Что делать",
        "offseason": "Сейчас вне поливного сезона ({season}). Мониторинг продолжается.",
        "live": "📡 Живые данные: наблюдения по {date}, прогноз ECMWF на 6 недель вперёд",
        "snapshot": "Данные на {date}",
        "replay": "⏪ Повтор прошлого: фактические данные за {date}, это не прогноз",
    },
    "kk": {
        "district": "Аудан",
        "deficit": "14 күндегі ылғал тапшылығы (булану − жауын-шашын): {d} мм, қалыпты деңгей {n} мм",
        "surplus": "14 күндегі ылғал артықшылығы (жауын-шашын − булану): {d} мм",
        "dryness": "Құрғақтық: {p}-перцентиль (1991–2020 жж. нормасымен салыстырғанда)",
        "prob": "Алдағы 6 аптада құрғақ кезең болу ықтималдығы: {p} % (ECMWF болжамының {n} сценарийінің {k}-і)",
        "onset": "Күтілетін басталуы: {date} ({d} күннен кейін)",
        "onset_actual": "Құрғақ кезең іс жүзінде басталды: {date}",
        "ai": "ECMWF AIFS AI-моделі, 2 апта: {n} сценарийдің {k}-і",
        "todo": "Не істеу керек",
        "offseason": "Қазір суару маусымы емес ({season}). Бақылау жалғасуда.",
        "live": "📡 Нақты деректер: {date} дейінгі бақылаулар, ECMWF-тің алдағы 6 аптаға болжамы",
        "snapshot": "Деректер {date} күнгі жағдай бойынша",
        "replay": "⏪ Өткен кезеңді қайталау: {date} күнгі нақты деректер, бұл болжам емес",
    },
}


def _scen(n: int) -> str:
    """Russian genitive after 'из N': из 51 сценария, из 50 сценариев."""
    return "сценария" if n % 10 == 1 and n % 100 != 11 else "сценариев"


def message(a: Assessment, region: dict, lang: str = "ru") -> str:
    lang = lang if lang in TITLE else "en"
    L = LABELS[lang]
    if a.deficit_mm < 0:
        water = L["surplus"].format(d=round(-a.deficit_mm))
    else:
        water = L["deficit"].format(d=round(a.deficit_mm), n=round(a.norm_mm))
        if a.anomaly_pct is not None:
            water += f" ({a.anomaly_pct:+.0f} %)"
    lines = [f"{EMOJI[a.level]} *{TITLE[lang][a.level]}*",
             f"{L['district']}: {region[lang]}",
             water,
             L["dryness"].format(p=round(a.current_pct))]
    replay = a.source == "replay"
    if not replay:
        lines.append(L["prob"].format(p=round(100 * a.p_dry), k=a.n_dry, n=a.n_members, scen=_scen(a.n_members)))
    if a.onset_date is not None:
        key = "onset_actual" if replay else "onset"
        lines.append(L[key].format(date=f"{a.onset_date:%d.%m.%Y}", d=a.days_to_onset))
    if a.ai is not None:
        lines.append(L["ai"].format(k=a.ai["n_dry"], n=a.ai["n_members"], scen=_scen(a.ai["n_members"])))
    lines.append("")
    if a.in_season:
        lines.append(f"*{L['todo']}:*")
        lines += [f"• {x}" for x in ACTIONS[lang][a.level]]
    else:
        lines.append(L["offseason"].format(season=season_label()))
    lines += ["", L[a.source].format(date=f"{a.as_of:%d.%m.%Y}")]  # every message says how fresh it is
    return "\n".join(lines)


def season_label() -> str:
    """Irrigation season as 'DD.MM – DD.MM'."""
    (m1, d1), (m2, d2) = config.SEASON_START, config.SEASON_END
    return f"{d1:02d}.{m1:02d} – {d2:02d}.{m2:02d}"
