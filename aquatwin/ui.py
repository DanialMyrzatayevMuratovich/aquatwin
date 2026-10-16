"""Presentation helpers. Every value comes from the shared assessment engine."""
from html import escape
from pathlib import Path
import re

import streamlit as st

from . import advice

COLORS = {"low": "#28886c", "moderate": "#d39b34", "high": "#d66a54", "ongoing": "#9b6554"}
LEVELS = {"low": "Low risk", "moderate": "Watch", "high": "High risk", "ongoing": "Ongoing"}
BACKGROUNDS = {"low": "#e4f2e9", "moderate": "#fff2d6", "high": "#fbe8e1", "ongoing": "#efe1db"}
PILL_TEXT = {"low": "#21654e", "moderate": "#8f641d", "high": "#9e4534", "ongoing": "#754535"}


def html(content):
    st.markdown(content, unsafe_allow_html=True)


def styles():
    css = (Path(__file__).resolve().parents[1] / "assets" / "dashboard.css").read_text(encoding="utf-8")
    html(f"<style>{css}</style>")


def icon(name, size=20):
    paths = {
        "map": '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3Z"/><path d="M9 3v15M15 6v15"/>',
        "chart": '<path d="M3 3v18h18M6 15l5-5 4 3 6-8"/>',
        "send": '<path d="m22 2-7 20-4-9-9-4 20-7ZM22 2 11 13"/>',
        "water": '<path d="M12 2S4 10 4 15a8 8 0 0 0 16 0c0-5-8-13-8-13Z"/><path d="M8 15a4 4 0 0 0 4 4"/>',
    }
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def brand():
    return '<div class="brand"><svg class="brand-mark" viewBox="0 0 36 42" aria-hidden="true"><path d="M18 1C13 10 3 19 3 27a15 15 0 0 0 30 0C33 19 23 10 18 1Z" fill="#56b8a0"/><path d="M6 29c6-7 15-2 24-9 7 19-19 28-24 9" fill="#bde694"/></svg>AquaTwin<span style="font-size:10px;letter-spacing:1px;font-weight:500;margin-left:3px;opacity:.6">BETA</span></div>'


def login_hero():
    # Decorative field illustration, not a satellite image or a map of measured risk.
    art = '''<svg class="field-art" viewBox="0 0 520 240" role="img" aria-label="Illustration of irrigated fields and a water channel">
    <defs><pattern id="rows" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(-25)"><path d="M0 0v12" stroke="#c4dc97" stroke-width="2" opacity=".4"/></pattern></defs>
    <g transform="translate(260,116) rotate(-14)"><rect x="-230" y="-85" width="150" height="85" rx="7" fill="#447555"/><rect x="-67" y="-85" width="130" height="85" rx="7" fill="#84a56b"/><rect x="76" y="-85" width="150" height="85" rx="7" fill="#58774c"/><rect x="-230" y="15" width="95" height="92" rx="7" fill="#779760"/><rect x="-122" y="15" width="185" height="92" rx="7" fill="#496d4c"/><rect x="76" y="15" width="150" height="92" rx="7" fill="#a1b576"/><rect x="-230" y="-85" width="456" height="192" rx="7" fill="url(#rows)"/><path d="M-247 7H242" stroke="#5bb4a2" stroke-width="6"/><path d="M69-103V125" stroke="#5bb4a2" stroke-width="5"/><circle cx="-9" cy="-42" r="27" fill="none" stroke="#d6e8bc" opacity=".6"/><circle cx="-9" cy="-42" r="6" fill="#d6e8bc"/><path d="m-9-42 22-14" stroke="#d6e8bc"/></g>
    <g transform="translate(306,128)"><rect width="165" height="62" rx="12" fill="#f7faef"/><circle cx="22" cy="23" r="5" fill="#2d997a"/><text x="35" y="27" fill="#244b38" font-family="Arial" font-size="12" font-weight="700">Every drop matters.</text><text x="17" y="46" fill="#7b8d76" font-family="Arial" font-size="10">Weather data. Clearer decisions.</text></g></svg>'''
    html(f'<div class="login-hero">{brand()}<div class="eyebrow">Water intelligence for Kazakhstan</div><h1>A clearer outlook.<br><em>A better water plan.</em></h1><p>Understand changing drought conditions. Turn weather scenarios into practical information for your district.</p>{art}<div class="login-bottom"><span>8 configured districts</span><span>3 languages</span><span>1 shared outlook</span></div></div>')


def section(title, name, sub=""):
    html(f'<div class="section-title">{icon(name)}{escape(title)}</div>' + (f'<div class="subtle">{escape(sub)}</div>' if sub else ''))


def district_list(df, lang, selected):
    rows = []
    for _, r in df.sort_values("current_pct").iterrows():
        level = r["level"]
        detail = f'Percentile {r["current_pct"]:.0f} · historical replay' if r["source"] == "replay" else f'{r["p_dry"]:.0f}% of forecast scenarios'
        rows.append(f'<div class="district-row {"selected" if r["id"] == selected else ""}"><div><div class="district-name"><span class="dot" style="background:{COLORS[level]};margin-right:7px"></span>{escape(r[lang])}</div><div class="district-meta">{detail}</div></div><span class="risk-pill" style="color:{PILL_TEXT[level]};background:{BACKGROUNDS[level]}">{LEVELS[level]}</span></div>')
    html("".join(rows))


def focus(a, region, lang):
    historical = a.source == "replay"
    number = f'{a.current_pct:.0f}<small> / 100 percentile</small>' if historical else f'{100*a.p_dry:.0f}<small>% of scenarios</small>'
    explanation = "Water balance compared with the historical norm. Lower means drier than usual." if historical else f"{a.n_dry} of {a.n_members} ECMWF scenarios contain a dry spell in the next six weeks."
    html(f'<div class="focus-card"><div class="eyebrow">{"Historical assessment" if historical else "District outlook"} · {a.as_of:%d %b %Y}</div><span class="risk-pill">{LEVELS[a.level]}</span><h2>{escape(region[lang])}</h2><div class="focus-number">{number}</div><p>{explanation}</p></div>')


def stats(a):
    onset = a.onset_date.strftime("%d %b") if a.onset_date is not None else "—"
    onset_label = "Actual dry-spell onset" if a.source == "replay" else "Median scenario onset"
    onset_note = "Known historical outcome" if a.source == "replay" else "Among scenarios with a dry spell"
    if a.onset_date is None:
        onset_note = "No onset detected in this window"
    water_label = "14-day water deficit" if a.deficit_mm >= 0 else "14-day water surplus"
    water_note = f"Normal deficit: {a.norm_mm:.0f} mm" if a.deficit_mm >= 0 else "Rain exceeds reference evaporation"
    html(f'<div class="detail-stats"><div class="detail-stat"><div class="subtle">{water_label}</div><div class="value">{abs(a.deficit_mm):.0f} <small>mm</small></div><div class="subtle">{water_note}</div></div><div class="detail-stat"><div class="subtle">{onset_label}</div><div class="value">{onset}</div><div class="subtle">{onset_note}</div></div></div>')
    value = max(0, min(100, a.current_pct))
    html(f'<div class="detail-stat"><div class="subtle">Water-balance percentile</div><div class="value">{a.current_pct:.0f}<small> / 100 · lower means drier</small></div><div class="percentile-scale"><span class="percentile-marker" style="left:calc({value:.1f}% - 2px)"></span></div><div class="scale-labels"><span>Unusually dry</span><span>Wetter than usual</span></div></div>')


def action_card(a, lang):
    if a.in_season:
        actions = advice.ACTIONS[lang][a.level]
        title = {"en": "Suggested actions", "ru": "Рекомендуемые действия", "kk": "Ұсынылатын әрекеттер"}[lang]
    else:
        title = "Monitoring mode"
        actions = [advice.LABELS[lang]["offseason"].format(season=advice.season_label())]
    rows = ''.join(f'<div class="action"><span class="action-num">{i}</span><span>{escape(text)}</span></div>' for i,text in enumerate(actions,1))
    note = "Example actions for this historical case. " if a.source == "replay" else ""
    html(f'<div class="actions"><h4>{title}</h4>{rows}<div class="subtle" style="margin-top:16px">{note}Prototype guidance · agronomic review pending.</div></div>')


def telegram(a, region, lang):
    message = escape(advice.message(a, region, lang))
    message = re.sub(r"\*(.+?)\*", r"<b>\1</b>", message).replace("\n", "<br>")
    html(f'<div class="phone"><div class="phone-header"><div class="telegram-avatar">{icon("send")}</div><div><strong>AquaTwin Bot</strong><div class="subtle">Telegram message preview · {lang.upper()}</div></div></div><div class="phone-body"><div class="bubble">{message}</div></div><div class="phone-footer">Shared assessment engine · replies when the farmer requests an update</div></div>')
