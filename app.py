"""AquaTwin dashboard. Run: streamlit run app.py"""
import datetime as dt
import hmac
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from aquatwin import advice, config, data, drought, ui

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
st.set_page_config(page_title="AquaTwin · Water outlook", page_icon="💧", layout="wide")
ui.styles()


def require_login() -> None:
    """Sign-in gate; hosting credentials stay in environment variables."""
    user, password = os.environ.get("DASHBOARD_USER", ""), os.environ.get("DASHBOARD_PASSWORD", "")
    if not (user and password) or st.session_state.get("signed_in"):
        return
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        ui.login_hero()
    with right:
        ui.html('<div class="login-intro"><div class="eyebrow">Your water-planning workspace</div><h2>Welcome back.</h2><p>Sign in to explore your district’s water outlook.</p></div>')
        with st.form("login"):
            login = st.text_input("Login", placeholder="Your account email")
            secret = st.text_input("Password", type="password", placeholder="Enter your password")
            if st.form_submit_button("Sign in", type="primary", width="stretch"):
                same_user = hmac.compare_digest(login.strip().lower().encode(), user.strip().lower().encode())
                if same_user & hmac.compare_digest(secret.encode(), password.encode()):
                    st.session_state["signed_in"] = True
                    st.rerun()
                time.sleep(1)
                st.error("Wrong login or password.")
            st.caption("Access is provided by the AquaTwin team.")
        ui.html('<div class="login-note">District insights · Historical replay · Farmer messages</div>')
        st.link_button("Explore AquaTwin on Telegram ↗", "https://t.me/AquaTwin_Bot", width="stretch")
    ui.html('<div class="footer"><span>AquaTwin / Tomorrow School</span><span>Built for water planning in southern Kazakhstan</span></div>')
    st.stop()


require_login()
REPLAY_MIN, REPLAY_MAX = dt.date(1991, 4, 1), dt.date(2025, 11, 15)
DEFAULT_REPLAY = os.environ.get("AQUATWIN_DEFAULT_MODE", "live").strip().lower() == "replay"

with st.sidebar:
    ui.html(ui.brand())
    ui.html('<div class="eyebrow">Workspace</div>')
    st.markdown("**Water outlook**")
    st.caption("Turkistan & Kyzylorda\n\n8 configured districts")
    st.divider()
    lang = st.selectbox("Language / Тіл / Язык", ["en", "ru", "kk"], index=0)
    replay = st.radio("Data", ["Live forecast", "Replay of the past"], index=int(DEFAULT_REPLAY),
                      help="Replay uses bundled historical data. Map tiles may need internet.") != "Live forecast"
    replay_date = None
    if replay:
        replay_date = st.date_input("Replay date", dt.date.fromisoformat(config.REPLAY_DEFAULT_DATE),
                                    min_value=REPLAY_MIN, max_value=REPLAY_MAX).isoformat()
    if st.button("Refresh data", width="stretch", icon=":material/refresh:"):
        st.cache_data.clear()
    st.divider()
    st.link_button("Open Telegram bot ↗", "https://t.me/AquaTwin_Bot", width="stretch")
    with st.expander("About the data"):
        st.caption("ERA5 · 1991–2020 reference\n\nECMWF EC46 · 6-week ensemble\n\nECMWF AIFS · 2-week comparison\n\nData provided via Open-Meteo. District estimates, not field measurements.")
    if st.session_state.get("signed_in") and st.button("Sign out", width="stretch"):
        st.session_state.clear()
        st.rerun()


@st.cache_data(ttl=3600, show_spinner="Preparing the district water outlook…")
def run_all(mode: str, replay_date: str | None, today: dt.date):
    def one(region):
        return drought.assess(data.load_region(region, today=today, mode=mode, replay_date=replay_date))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, config.REGIONS))
    rows = [{**r, **a.summary()} for r, a in zip(config.REGIONS, results)]
    return pd.DataFrame(rows), {r["id"]: a for r, a in zip(config.REGIONS, results)}


ui.html('<div class="topline"><div class="eyebrow" style="margin:0">Overview / Southern Kazakhstan</div><span class="tag"><span class="dot"></span>AquaTwin workspace</span></div>')
st.title("Every drop. A clearer decision.")
ui.html('<p class="subtitle">A district-level view of changing drought conditions and water-planning priorities.</p>')
df, details = run_all("replay" if replay else "live", replay_date, data.utc_today())
sources = set(df["source"])
as_of = df["as_of"].max()

if replay:
    st.info(f"Historical replay · {as_of} — the dotted line shows what actually happened next, not a forecast.", icon=":material/history:")
elif "replay" in sources:
    st.warning("Some current data could not be loaded. Showing a replay of real history for affected districts — not a forecast. Check each district’s source and date.")
elif "snapshot" in sources:
    st.warning("Some APIs are unavailable. Saved results are shown for affected districts. Check each district’s source and date.")
else:
    st.caption(f"Live model data · latest observations through {as_of} · ECMWF forecast horizon: 6 weeks")
if not df["in_season"].all():
    st.info(f"Outside the irrigation season ({advice.season_label()}). Monitoring continues; irrigation advice is paused.", icon="ℹ️")

for col, lvl in zip(st.columns(4), ("high", "moderate", "ongoing", "low")):
    with col.container(key=f"risk_{lvl}"):
        st.metric(ui.LEVELS[lvl] + " districts", int((df["level"] == lvl).sum()))
st.caption("In replay, these are retrospective scenario classifications; they are not measured forecast probabilities." if "replay" in sources else "Risk levels come from the share of ECMWF scenarios with a dry spell and the current water-balance indicator.")

name_by_id = df.set_index("id")[lang].to_dict()
rid = st.selectbox("District", df["id"], format_func=name_by_id.get, key="selected_district")
a = details[rid]
region = next(r for r in config.REGIONS if r["id"] == rid)
left, right = st.columns([1.7, 1], gap="large")
with left:
    with st.container(border=True):
        ui.section("Regional overview", "map", "Turkistan & Kyzylorda · district centres")
        fig = px.scatter_map(df, lat="lat", lon="lon", color="level", color_discrete_map=ui.COLORS,
                             hover_name=lang, hover_data={"current_pct": ":.0f", "lat": False, "lon": False},
                             size=[20 if i == rid else 13 for i in df["id"]], zoom=5, height=375,
                             center={"lat":float(df["lat"].mean()), "lon":float(df["lon"].mean())})
        fig.update_layout(map_style="carto-positron", showlegend=False, margin=dict(l=0,r=0,t=10,b=0),
                          paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar":False})
        ui.html('<div class="legend">'+''.join(f'<span><i class="dot" style="background:{c}"></i>{ui.LEVELS[k]}</span>' for k,c in ui.COLORS.items())+'</div>')
with right:
    with st.container(border=True):
        ui.section("Across the districts", "water", "Ordered from the lowest water-balance percentile")
        ui.district_list(df, lang, rid)

st.subheader("District detail")
st.caption(f"{region[lang]} · Source: {a.source} · observations through {a.as_of:%d %b %Y}")
focus, numbers = st.columns([1, 1.6], gap="large")
with focus:
    ui.focus(a, region, lang)
with numbers:
    ui.stats(a)

with st.container(border=True):
    ui.section("How conditions change", "chart", "Water-balance percentile · lower values mean drier than usual")
    obs, fc = (a.timeline[a.timeline["kind"] == kind] for kind in ("observed", "forecast"))
    historical = a.source == "replay"
    g = go.Figure()
    g.add_trace(go.Scatter(mode="lines", x=obs.index, y=obs["percentile"], name="Observed", line=dict(color="#205a49",width=3)))
    if not historical:
        g.add_trace(go.Scatter(mode="lines",x=fc.index,y=fc["p90"],line=dict(width=0),showlegend=False,hoverinfo="skip"))
        g.add_trace(go.Scatter(mode="lines",x=fc.index,y=fc["p10"],name="EC46: 10–90% of scenarios",fill="tonexty",line=dict(width=0),fillcolor="rgba(35,143,154,.13)"))
    g.add_trace(go.Scatter(mode="lines",x=fc.index,y=fc["percentile"],line=dict(color="#238f9a",width=3,dash="dot"),name="What actually happened" if historical else "EC46: median"))
    if a.ai is not None:
        ai = a.ai["timeline"]
        g.add_trace(go.Scatter(mode="lines",x=ai.index,y=ai["p90"],line=dict(width=0),showlegend=False,hoverinfo="skip"))
        g.add_trace(go.Scatter(mode="lines",x=ai.index,y=ai["p10"],name="AIFS: 10–90% of scenarios",fill="tonexty",line=dict(width=0),fillcolor="rgba(137,113,176,.12)"))
        g.add_trace(go.Scatter(mode="lines",x=ai.index,y=ai["percentile"],name="AIFS AI: median",line=dict(color="#8971b0",width=2,dash="dash")))
    g.add_hrect(y0=0,y1=config.FD_LOW_PCT,fillcolor="#d66a54",opacity=.08,line_width=0)
    g.add_hline(y=config.FD_LOW_PCT,line_color="#dbb2a4",line_dash="dot",annotation_text="Dry threshold · 20")
    g.add_hline(y=config.FD_HIGH_PCT,line_color="#bdcfc2",line_dash="dash",annotation_text="40th percentile")
    g.add_vline(x=a.as_of,line_color="#9aac9f",line_dash="dot")
    if a.onset_date is not None:
        g.add_vline(x=a.onset_date,line_color="#d66a54")
    g.update_layout(template="plotly_white",height=350,margin=dict(l=12,r=30,t=15,b=20),
                    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Arial",color="#60796c",size=12),yaxis_range=[0,100],
                    yaxis_title="Percentile",yaxis_gridcolor="#e9eee9",xaxis_showgrid=False,
                    legend=dict(orientation="h",y=-.2,x=0,font_size=11),hovermode="x unified")
    st.plotly_chart(g,width="stretch",config={"displayModeBar":False})
    if a.ai is not None:
        st.caption("The purple AIFS line is an AI-model comparison. It does not set the main risk level; forecast skill has not been validated yet.")
    if historical:
        st.caption("The dotted line is the known historical outcome. This replay is not a forecast backtest.")

left, right = st.columns([1,1.2], gap="large")
with left:
    ui.section("From insight to action", "water", "Practical context for water planning")
    ui.html('<div class="flow"><span>Weather data</span>→<span>District outlook</span>→<span>Farmer message</span></div>')
    ui.action_card(a,lang)
with right:
    ui.section("The farmer’s view", "send", "Message the farmer receives in Telegram:")
    st.caption("Change the language in the sidebar to preview the same message in English, Kazakh or Russian.")
    ui.telegram(a,region,lang)

with st.expander("Compare all district values"):
    table = df[[lang,"source","as_of","level","current_pct","deficit_mm","norm_mm","p_dry","ai_p_dry","onset_date"]].copy()
    table.columns = ["District","Source","As of","Level","Percentile","Deficit mm","Normal mm","EC46 %","AIFS %","Onset"]
    st.dataframe(table.astype(object).where(table.notna(),"—"),hide_index=True,width="stretch")
    st.caption("Percentile: 14-day rain minus reference evaporation compared with 1991–2020. EC46 and AIFS percentages: share of scenarios with a dry spell. A dash means not available; replay has no ensemble probability.")
with st.expander("How to read this outlook"):
    st.markdown("**Water balance:** rainfall minus FAO-56 reference evapotranspiration over 14 days.\n\n"
                "**Historical reference:** ERA5, 1991–2020, for the same time of year. A low percentile means unusually dry conditions.\n\n"
                f"**Dry-spell rule:** a fall from ≥{config.FD_HIGH_PCT} to ≤{config.FD_LOW_PCT} within {config.FD_WINDOW_DAYS} days, with a persistence criterion of {config.FD_MIN_DRY_DAYS} days. Thresholds adapted from soil-moisture research.\n\n"
                "**Scope:** district estimates from 25–36 km grids. Forecast skill and recommendations still need independent validation.")
ui.html('<div class="footer"><span>AquaTwin · Tomorrow School</span><span>ERA5 / ECMWF / Open-Meteo · Prototype for district-level planning</span></div>')
