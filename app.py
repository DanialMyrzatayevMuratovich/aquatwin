"""AquaTwin dashboard.  Run:  streamlit run app.py"""
import datetime as dt
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from aquatwin import advice, config, data, drought

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
st.set_page_config(page_title="AquaTwin", page_icon="💧", layout="wide")

COLORS = {"low": "#2e9e5b", "moderate": "#e0a800", "high": "#d6372b", "ongoing": "#7a4b2a"}
EC46_COLOR, AI_COLOR = "#1f77b4", "#8e44ad"
REPLAY_MIN, REPLAY_MAX = dt.date(1991, 4, 1), dt.date(2025, 11, 15)

with st.sidebar:
    st.title("💧 AquaTwin")
    st.caption("Flash-drought early warning for farmers in arid regions")
    lang = st.selectbox("Language / Тіл / Язык", ["en", "ru", "kk"], index=0)
    replay = st.radio("Data", ["Live forecast", "Replay of the past"], index=0,
                      help="Replay shows real history for a chosen date. It needs no internet.") != "Live forecast"
    replay_date = None
    if replay:
        replay_date = st.date_input("Replay date", dt.date.fromisoformat(config.REPLAY_DEFAULT_DATE),
                                    min_value=REPLAY_MIN, max_value=REPLAY_MAX).isoformat()
    if st.button("Refresh data"):
        st.cache_data.clear()
    st.markdown("**Data (via Open-Meteo):** ERA5 1991–2020 norm · ECMWF EC46 ensemble, 51 scenarios, 6 weeks · "
                "ECMWF AIFS AI ensemble, 2 weeks")


@st.cache_data(ttl=3600, show_spinner="Loading water-balance data…")
def run_all(mode: str, replay_date: str | None, today: dt.date):
    def one(region):
        return drought.assess(data.load_region(region, today=today, mode=mode, replay_date=replay_date))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, config.REGIONS))
    rows = [{**r, **a.summary()} for r, a in zip(config.REGIONS, results)]
    return pd.DataFrame(rows), {r["id"]: a for r, a in zip(config.REGIONS, results)}


df, details = run_all("replay" if replay else "live", replay_date, data.utc_today())
sources = set(df["source"])
as_of = df["as_of"].max()

st.header("Turkistan & Kyzylorda pilot — dry-spell outlook for the next 6 weeks")
if replay:
    st.info(f"⏪ Replay of the past: real data as of {as_of}. The dotted line is what actually happened next, "
            "not a forecast.")
elif "replay" in sources:
    st.warning(f"No connection to the data APIs. Showing a replay of real history ({as_of}) — this is not a forecast.")
elif "snapshot" in sources:
    st.warning(f"The data APIs are not responding. Showing the last saved result (observations through {as_of}).")
else:
    st.caption(f"🟢 Live data · observations through {as_of} · risk = share of 51 ECMWF ensemble scenarios "
               "with a dry spell")
if not df["in_season"].all():
    st.info(f"Outside the irrigation season ({advice.season_label()}): levels are shown for monitoring, "
            "farmers get no irrigation advice.")

for col, lvl in zip(st.columns(4), ("high", "ongoing", "moderate", "low")):
    col.metric(advice.TITLE[lang][lvl], int((df["level"] == lvl).sum()))

left, right = st.columns([2, 3])  # the table needs more room than the map
with left:
    fig = px.scatter_map(
        df, lat="lat", lon="lon", color="level", color_discrete_map=COLORS, hover_name=lang,
        hover_data={"current_pct": True, "p_dry": True, "onset_date": True, "lat": False, "lon": False},
        size=[18] * len(df), zoom=5, height=440,
        center={"lat": float(df["lat"].mean()), "lon": float(df["lon"].mean())},
    )
    fig.update_layout(map_style="open-street-map", margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, width="stretch")
with right:
    table = df.sort_values(["p_dry", "current_pct"], ascending=[False, True], na_position="last")
    table = table[[lang, "level", "current_pct", "deficit_mm", "norm_mm", "p_dry", "ai_p_dry", "onset_date"]]
    table.columns = ["District", "Level", "Dryness", "Deficit", "Normal", "Dry spell %", "AI 2 wk %", "Onset"]
    st.dataframe(table.astype(object).where(table.notna(), "—"), hide_index=True, width="stretch")
    st.caption("Dryness: percentile of the 14-day water balance (rain − evaporation) against 1991–2020; "
               "low = drier than usual. Deficit and Normal: evaporation − rain over 14 days, mm. "
               "Dry spell %: share of ECMWF scenarios with a dry spell in 6 weeks. "
               "AI 2 wk %: the same for the ECMWF AIFS AI ensemble over 2 weeks.")

st.subheader("District detail")
rid = st.selectbox("District", df["id"], format_func=lambda i: df.set_index("id").loc[i, lang])
a = details[rid]
region = next(r for r in config.REGIONS if r["id"] == rid)
obs, fc = (a.timeline[a.timeline["kind"] == kind] for kind in ("observed", "forecast"))
single = a.n_members == 1

g = go.Figure()
g.add_trace(go.Scatter(mode="lines", x=obs.index, y=obs["percentile"], name="observed", line=dict(color="#222", width=3)))
if not single:
    g.add_trace(go.Scatter(mode="lines", x=fc.index, y=fc["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    g.add_trace(go.Scatter(mode="lines", x=fc.index, y=fc["p10"], name="ECMWF EC46: 10–90 % of scenarios", fill="tonexty",
                           line=dict(width=0), fillcolor="rgba(31,119,180,0.18)"))
g.add_trace(go.Scatter(mode="lines", x=fc.index, y=fc["percentile"], line=dict(color=EC46_COLOR, width=3, dash="dot"),
                       name="what actually happened" if single else "ECMWF EC46: median"))
if a.ai is not None:
    ai = a.ai["timeline"]
    g.add_trace(go.Scatter(mode="lines", x=ai.index, y=ai["p90"], line=dict(width=0), showlegend=False, hoverinfo="skip"))
    g.add_trace(go.Scatter(mode="lines", x=ai.index, y=ai["p10"], name="ECMWF AIFS (AI): 10–90 %", fill="tonexty",
                           line=dict(width=0), fillcolor="rgba(142,68,173,0.18)"))
    g.add_trace(go.Scatter(mode="lines", x=ai.index, y=ai["percentile"], name="ECMWF AIFS (AI): median",
                           line=dict(color=AI_COLOR, width=2, dash="dash")))
g.add_hrect(y0=0, y1=config.FD_LOW_PCT, fillcolor="#d6372b", opacity=0.10, line_width=0,
            annotation_text=f"dry (≤{config.FD_LOW_PCT}th pct)")
g.add_hline(y=config.FD_HIGH_PCT, line_dash="dash", line_color="gray", annotation_text=f"{config.FD_HIGH_PCT}th pct")
if a.onset_date is not None:
    g.add_vline(x=a.onset_date, line_color="#d6372b")
g.update_layout(height=400, yaxis_title="Water-balance percentile (low = dry)", yaxis_range=[0, 100],
                margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", y=-0.15))
st.plotly_chart(g, width="stretch")
if a.ai is not None:
    st.caption("The AI model (ECMWF AIFS) is shown for comparison and does not affect the risk level: "
               "we have not verified it on past seasons yet.")

st.markdown("**Message the farmer receives in Telegram:**")
with st.container(border=True):
    # Telegram renders *bold* and keeps line breaks; Streamlit Markdown needs **bold** and hard breaks.
    st.markdown(re.sub(r"\*(.+?)\*", r"**\1**", advice.message(a, region, lang)).replace("\n", "  \n"))
st.caption("Method: 14-day water balance (precipitation − FAO-56 reference evapotranspiration) as a percentile of "
           "the ERA5 1991–2020 norm. A dry spell in a scenario = the percentile falls from "
           f"≥{config.FD_HIGH_PCT} to ≤{config.FD_LOW_PCT} within {config.FD_WINDOW_DAYS} days and stays there for "
           f"{config.FD_MIN_DRY_DAYS} days. District-level accuracy (25–36 km grids), not field-level.")
