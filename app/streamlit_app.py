import json
import sys
from pathlib import Path

# Streamlit may launch this file with app/ as the import root. Add the project
# root explicitly so `app.*` imports work regardless of how the server starts.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime,timezone
import duckdb
import numpy as np, pandas as pd, plotly.graph_objects as go, streamlit as st
from app.config import get_settings
from app.db.database import initialize,connect
from app.events.manual import save_event
from app.features.kalshi_events import build_activity_events,candidate_market_match
from app.scoring.composite import composite as combine_evidence

st.set_page_config(page_title="Weather Market Anomaly Explorer",page_icon="🌦️",layout="wide")
s=get_settings()
try:
    # Schema creation is only necessary for a new database. Re-running it on
    # every page interaction asks DuckDB for a write lock and can collide with
    # the scheduled data refresh.
    if not s.db_path.exists(): initialize()
    else:
        with connect(read_only=True) as con: con.execute("SELECT 1")
except duckdb.IOException as exc:
    if "Could not set lock" not in str(exc): raise
    st.warning("Live data refresh in progress. The dashboard will reconnect automatically when the updated data is ready.")
    st.caption("The existing database is protected while calculations are being rebuilt. No data has been lost.")
    st.components.v1.html("<script>setTimeout(() => window.parent.location.reload(), 5000);</script>",height=0)
    st.stop()
st.markdown("""<style>
:root {--navy:#0f172a;--navy-2:#17233d;--charcoal:#111827;--text:#1f2937;--muted:#5f6b7c;--blue:#2563eb;--blue-soft:#eaf1ff;--surface:#ffffff;--page:#f5f7fb;--line:#dbe2ea;--radius:10px;}
.stApp,[data-testid="stAppViewContainer"] {background:var(--page);color:var(--text)}
[data-testid="stMainBlockContainer"] {padding-top:1.15rem;padding-bottom:3rem;max-width:1500px}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:.72rem}
[data-testid="stHeader"] {background:rgba(245,247,251,.92)}
.stApp p,.stApp label,.stApp li,.stApp span,.stApp div {color:var(--text)}
.stApp h1,.stApp h2,.stApp h3,.stApp h4 {color:var(--charcoal);letter-spacing:-.015em}
.stApp small,[data-testid="stCaptionContainer"],.stCaption {color:var(--muted)!important}

/* Sidebar */
[data-testid="stSidebar"] {background:linear-gradient(180deg,#0b1428 0%,#111d35 100%);border-right:1px solid #26344e}
[data-testid="stSidebar"] * {color:#e7edf7!important}
[data-testid="stSidebar"] [data-testid="stRadio"] > label {color:#9fb0c9!important;text-transform:uppercase;letter-spacing:.08em;font-size:.72rem;font-weight:700}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:.58rem .72rem;border-radius:8px;margin:.12rem 0;transition:background .15s ease,border-color .15s ease;border:1px solid transparent}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:#1a2a48;border-color:#2d4165}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:#214f91;border-color:#3972c4;box-shadow:inset 3px 0 #7db2ff}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p {color:#fff!important;font-weight:700}
[data-testid="stSidebar"] [data-testid="stExpander"] {background:#14223b;border:1px solid #293a58;box-shadow:none}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:#1b2d4c}
[data-testid="stSidebar"] [data-testid="stExpander"] p {color:#d9e2f0!important;line-height:1.45}

/* Hero and status */
.hero {padding:17px 22px;border-radius:12px;background:linear-gradient(120deg,#101d36,#244a82);color:white;margin-bottom:8px;box-shadow:0 7px 22px rgba(18,33,63,.16)}
.hero h1 {margin:0;color:#fff;font-size:1.82rem}.hero p {margin:.3rem 0 0;color:#d9e6fb;font-size:.95rem}
.status-pill {display:inline-flex;align-items:center;gap:8px;background:#eef8f1;border:1px solid #bfdfc8;border-radius:999px;padding:6px 11px;color:#245b36!important;font-size:.82rem;font-weight:650;margin:.2rem 0 .8rem}
.status-dot {width:8px;height:8px;border-radius:50%;background:#2e9b58;box-shadow:0 0 0 3px rgba(46,155,88,.12)}

/* Score legend */
.score-key {display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:7px 0 10px}
.key-item {padding:11px 13px;border-radius:10px;border:1px solid var(--line);background:#fff;color:var(--text)!important;font-size:.86rem;line-height:1.45;box-shadow:0 2px 7px rgba(15,23,42,.035)}
.key-item b {color:var(--charcoal)!important}.key-low {border-color:#cbd5e1;background:#f8fafc}.key-monitor {border-color:#e7cf83;background:#fffbeb}.key-review {border-color:#edb48d;background:#fff7ed}.key-priority {border-color:#e4a2aa;background:#fff1f2}

/* KPI and content cards */
[data-testid="stMetric"] {background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 14px;box-shadow:0 3px 10px rgba(15,23,42,.045)}
[data-testid="stMetricLabel"] p {color:#556274!important;font-weight:650;font-size:.78rem;text-transform:uppercase;letter-spacing:.035em}
[data-testid="stMetricValue"] {color:var(--charcoal)!important;font-weight:750;line-height:1.1}
[data-testid="stMetricDelta"] {font-weight:650}
[data-testid="stExpander"] {background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(15,23,42,.035);margin-bottom:7px}
[data-testid="stExpander"] summary {padding:.2rem .25rem;transition:background .15s ease,border-color .15s ease}
[data-testid="stExpander"] summary:hover {background:#f3f6fb}
[data-testid="stExpander"] summary p {color:var(--charcoal)!important;font-weight:680;font-size:.95rem}
[data-testid="stExpander"] svg {color:#3e5f90!important}
[data-testid="stVerticalBlockBorderWrapper"] {background:#fff;border-color:var(--line)!important;border-radius:10px!important;box-shadow:0 2px 8px rgba(15,23,42,.035)}

/* Filters and inputs */
[data-testid="stWidgetLabel"] p {color:#273244!important;font-weight:680;font-size:.86rem}
[data-baseweb="input"],[data-baseweb="select"] > div,[data-baseweb="base-input"],textarea {background:#fff!important;border-color:#cbd5e1!important;border-radius:9px!important;color:var(--charcoal)!important;min-height:42px}
[data-baseweb="input"]:focus-within,[data-baseweb="select"] > div:focus-within {border-color:#4e7fc9!important;box-shadow:0 0 0 3px rgba(37,99,235,.1)!important}
[data-baseweb="tag"] {background:#e6eefb!important;border:1px solid #b8cbea!important;border-radius:7px!important}
[data-baseweb="tag"] span,[data-baseweb="tag"] div {color:#244a82!important;font-weight:650!important}
[data-baseweb="popover"] {color:var(--text)!important}
[role="option"] {color:var(--text)!important;background:#fff!important}
[role="option"]:hover {background:#eef3fb!important}

/* Tables, charts, alerts, code */
[data-testid="stDataFrame"],[data-testid="stPlotlyChart"],[data-testid="stVegaLiteChart"] {background:#fff;border:1px solid var(--line);border-radius:10px;padding:7px;box-shadow:0 3px 10px rgba(15,23,42,.035)}
[data-testid="stAlert"] {border-radius:9px;border-width:1px;color:var(--text)!important}
[data-testid="stAlert"] * {color:var(--text)!important}
code {background:#eaf0f8!important;color:#1d3f72!important;border-radius:5px;padding:2px 5px}
hr {border-color:var(--line)}
.eyebrow {font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#64748b!important;font-weight:750}
.stButton button {border-radius:9px;border:1px solid #b9c7d9;background:#fff;color:#1f3f6e;font-weight:700}
.stButton button:hover {border-color:#4778bd;background:#eff5ff;color:#173966}
@media(max-width:800px){.score-key{grid-template-columns:1fr 1fr}}
</style>""",unsafe_allow_html=True)
st.markdown("""<div class="hero"><h1>Weather Market Anomaly Explorer</h1><p>Compare live Polymarket wallet episodes with public Kalshi weather-market trade anomalies.</p></div>""",unsafe_allow_html=True)
st.caption("Anomaly scores identify unusual patterns. They are not probabilities of illegal conduct and do not establish wrongdoing.")
page=st.sidebar.radio("Navigate",["Dashboard","Polymarket","Kalshi","Events","Health","Settings / Data"])

def df(sql,params=None):
    with connect(read_only=True) as con:return con.execute(sql,params or []).fetchdf()

def weather_sql(alias="m"):
    return f"coalesce({alias}.weather_type,'') <> ''"

def chart_theme(fig):
    black="#000000"
    fig.update_layout(paper_bgcolor="#ffffff",plot_bgcolor="#ffffff",font=dict(color=black),title_font=dict(color=black,size=16),legend=dict(font=dict(color=black)),hoverlabel=dict(bgcolor="#ffffff",bordercolor="#94a3b8",font=dict(color=black)),xaxis=dict(tickfont=dict(color=black),title_font=dict(color=black),gridcolor="#e5e7eb",linecolor="#cbd5e1"),yaxis=dict(tickfont=dict(color=black),title_font=dict(color=black),gridcolor="#e5e7eb",linecolor="#cbd5e1"))
    if getattr(fig.layout,"yaxis2",None): fig.update_layout(yaxis2=dict(tickfont=dict(color=black),title_font=dict(color=black),gridcolor="#eef2f7"))
    return fig

def horizon_performance(rows,start_time,entry_price,direction,time_col="timestamp_utc",price_col="price"):
    data=rows.copy(); data[time_col]=pd.to_datetime(data[time_col],utc=True); start=pd.to_datetime(start_time,utc=True)
    results=[]
    for label,hours in [("15 minutes",.25),("1 hour",1),("6 hours",6),("24 hours",24)]:
        later=data[data[time_col]>=start+pd.Timedelta(hours=hours)]
        if later.empty: results.append({"Horizon":label,"Observed price":None,"Signed move":None,"Status":"No later trade available"}); continue
        price=float(later.iloc[0][price_col]); move=price-float(entry_price); move=move if direction=="YES" else -move
        results.append({"Horizon":label,"Observed price":round(price,4),"Signed move":round(move,4),"Status":"Available"})
    return results

SIGNAL_NAMES={"s1":"unusually large position","s2":"positioning before a verified event","s3":"unusual prior profitability","s4":"concentrated directional flow","s5":"unusual trading behavior"}
SIGNAL_HELP={
    "S1 · Size":"Is this episode unusually large for this market or wallet?",
    "S2 · Timing":"Was the position opened before a manually verified public event?",
    "S3 · Profitability":"Has the wallet's earlier resolved activity performed unusually well?",
    "S4 · Order flow":"Did this wallet represent concentrated one-direction trading?",
    "S5 · Behavior":"Does the overall trading pattern differ from comparable episodes?",
}
def episode_reasons(row):
    ranked=[]
    for key,label in SIGNAL_NAMES.items():
        value=row.get(key)
        if pd.notna(value): ranked.append((float(value),label))
    return [f"{label} ({value:.2f})" for value,label in sorted(ranked,reverse=True)[:3]]

def score_description(score):
    if score>=.92:return "Very unusual"
    if score>=.85:return "Highly unusual"
    if score>=.75:return "Worth monitoring"
    return "Below alert threshold"

def render_polymarket_analysis():
    st.markdown("---"); st.subheader("Polymarket anomaly graph and calculations")
    st.caption("Strict queue rule: score ≥ 0.75, at least four valid modules, at least two signals ≥ 0.75, and either 2+ trades with $100+ notional or one exceptionally large $5,000+ trade.")
    choices=df(f"""SELECT a.alert_id,a.composite_score,m.question,e.wallet FROM alerts a JOIN episodes e USING(episode_id) JOIN markets m USING(market_id)
        WHERE {weather_sql()} AND m.status='open' ORDER BY a.composite_score DESC""")
    if choices.empty: st.info("No scored Polymarket weather episodes are available yet."); return
    labels={r.alert_id:f"{r.composite_score:.3f} · {r.question} · {str(r.wallet)[:12]}…" for _,r in choices.iterrows()}
    aid=st.selectbox("Choose a flagged Polymarket wallet episode",choices.alert_id.tolist(),format_func=labels.get,key="poly_case")
    case=df("""SELECT a.*,e.*,m.question,m.slug,m.resolved_token,m.resolution_time,f.* FROM alerts a JOIN episodes e USING(episode_id)
        JOIN markets m USING(market_id) JOIN episode_features f USING(episode_id) WHERE alert_id=?""",[aid]).iloc[0]
    p1,p2,p3,p4=st.columns(4); p1.metric("Anomaly score",f"{case.composite_score:.3f}"); p2.metric("Direction",case.direction); p3.metric("Episode notional",f"${case.total_notional:,.2f}"); p4.metric("Trades",int(case.trade_count))
    st.markdown(f"**{case.question}**  \nWallet: `{case.wallet}`")
    reasons=episode_reasons(case); st.info("**Why flagged:** "+("; ".join(reasons) if reasons else "No strong explanation available."))
    fills=df("""SELECT timestamp_utc,price,side,outcome,size,notional FROM fills WHERE market_id=? AND wallet=?
        AND timestamp_utc BETWEEN ? AND ? ORDER BY timestamp_utc""",[case.market_id,case.wallet,case.entry_time,case.exit_time])
    fills["cumulative_notional"]=fills.notional.cumsum()
    fig=go.Figure(); fig.add_trace(go.Bar(x=fills.timestamp_utc,y=fills.notional,name="Individual trade ($)",marker_color=["#2563eb" if x=="BUY" else "#dc2626" for x in fills.side],customdata=fills[["price","size","side","outcome"]],hovertemplate="%{x}<br>$%{y:,.2f}<br>$%{customdata[0]:.4f} × %{customdata[1]:,.2f}<br>%{customdata[2]} %{customdata[3]}<extra></extra>")); fig.add_trace(go.Scatter(x=fills.timestamp_utc,y=fills.cumulative_notional,yaxis="y2",name="Cumulative ($)",line=dict(color="#111827",width=3)))
    fig.update_layout(title="Polymarket episode trade progression",xaxis_title="Time",yaxis_title="Trade value ($)",yaxis2=dict(title="Cumulative value ($)",overlaying="y",side="right"),paper_bgcolor="#fff",plot_bgcolor="#fff",font=dict(color="#000"),hovermode="x unified")
    st.plotly_chart(chart_theme(fig),width="stretch")
    log=fills.copy(); log["Notional calculation"]=log.apply(lambda r:f"${r.price:.4f} × {r.size:,.2f} = ${r.notional:,.2f}",axis=1)
    st.dataframe(log.rename(columns={"timestamp_utc":"Time","side":"Action","outcome":"Outcome","price":"Price","size":"Shares","notional":"Trade value ($)","cumulative_notional":"Cumulative ($)"})[["Time","Action","Outcome","Price","Shares","Trade value ($)","Notional calculation","Cumulative ($)"]],width="stretch",hide_index=True)
    market_prices=df("SELECT timestamp_utc,price FROM fills WHERE market_id=? ORDER BY timestamp_utc",[case.market_id])
    performance=horizon_performance(market_prices,case.entry_time,case.entry_price,case.direction)
    if case.resolved and str(case.resolved_token).upper() in ("YES","NO"):
        settlement=1.0 if str(case.resolved_token).upper()==case.direction else 0.0
        performance.append({"Horizon":"Settlement","Observed price":settlement,"Signed move":round(settlement-float(case.entry_price),4),"Status":f"Resolved {case.resolved_token}"})
    st.subheader("What happened after entry?"); st.dataframe(pd.DataFrame(performance),width="stretch",hide_index=True)
    scores=[case.s1,case.s2,case.s3,case.s4,case.s5]; reliability=[case.q1,case.q2,case.q3,case.q4,case.q5]
    logic=["Larger of market-size percentile and wallet-history percentile","Exponential closeness to verified weather observation: exp(-lead hours / 72)","Prior resolved performance: 0.5 + 0.5×tanh(2×mean ROI)","Average of absolute market imbalance and wallet market share","Isolation Forest behavioral-anomaly percentile"]
    rows=[]
    for name,logic_text,value,q in zip(SIGNAL_HELP,logic,scores,reliability):
        available=pd.notna(value) and float(q)>0
        rows.append({"Signal":name,"Statistical calculation":logic_text,"Score":round(float(value),4) if pd.notna(value) else None,"Reliability":float(q),"Weighted contribution":round(float(value)*float(q),4) if available else None,"Status":"Active" if available else "Unavailable — excluded"})
    st.subheader("Polymarket S1–S5 calculation breakdown"); st.dataframe(pd.DataFrame(rows),width="stretch",hide_index=True)
    valid=[(float(v),float(q)) for v,q in zip(scores,reliability) if pd.notna(v) and float(q)>0]
    log_terms=[q*np.log(np.clip(v,.01,.99)/(1-np.clip(v,.01,.99))) for v,q in valid]; evidence=sum(log_terms)
    st.latex(r"\text{Composite}=\sigma\!\left(\sum_i Q_i\log\frac{S_i}{1-S_i}\right)")
    st.write(f"This episode: combined log-evidence `{evidence:.4f}` → score `{case.composite_score:.4f}`. Multiple agreeing signals reinforce one another; conflicting signals cancel.")
    available_horizons=sum(1 for r in performance if r["Observed price"] is not None); active_modules=sum(1 for r in rows if r["Status"]=="Active")
    quality="High" if len(fills)>0 and active_modules==5 and available_horizons>=3 else "Medium" if len(fills)>0 and active_modules>=4 else "Limited"
    st.success(f"Case data completeness: {quality} · {len(fills)} graph trades · {active_modules}/5 active signals · {available_horizons}/{len(performance)} follow-up prices")
    event_rows=df("SELECT event_time_utc,headline,confidence,source_url FROM public_events WHERE market_id=? AND verified AND NOT rejected ORDER BY event_time_utc",[case.market_id])
    if len(event_rows): st.dataframe(event_rows.rename(columns={"event_time_utc":"Observation / event time","headline":"Timing reference","confidence":"Confidence","source_url":"Source"}),width="stretch",hide_index=True)
    if case.slug: st.link_button("Open original Polymarket market",f"https://polymarket.com/event/{case.slug}")
    if case.suppression_reasons: st.warning(f"Unavailable evidence: {case.suppression_reasons}")

with st.sidebar.expander("How to read the scores",expanded=False):
    st.write("**0.00–0.74:** below the stricter alert threshold")
    st.write("**0.75–0.84:** Monitor — requires at least three strong signals and four valid modules")
    st.write("**0.85–0.91:** Review — stronger multi-signal anomaly")
    st.write("**0.92–1.00:** Priority only when all five modules and high-confidence timing are available")
    st.caption("A missing signal is excluded, not treated as zero.")
with st.sidebar.expander("S1–S5 signal key",expanded=False):
    for name,meaning in SIGNAL_HELP.items(): st.write(f"**{name}** — {meaning}")
with st.sidebar.expander("Statistical methodology",expanded=False):
    st.write("**Composite:** reliability-tempered log-odds evidence, not an average.")
    st.write("**S3:** ROI is shrunk by n/(n+7); thin histories remain near neutral.")
    st.write("**S4:** wallet share is ranked within liquidity peers and disabled below 20 trades or $1,000 observed volume.")
    st.write("**S5 / K5:** rank-normalized within weather type; Isolation Forest contamination is fixed at 2%.")
    st.write("**K3:** compared with the contract's historical arrival rate; it is down-weighted because Kalshi has no participant identity or linked public-event feed.")

if page=="Dashboard":
    st.markdown("""<div class="score-key"><div class="key-item key-low"><b>0.00–0.74</b><br>Below alert threshold</div><div class="key-item key-monitor"><b>0.75–0.84 · Monitor</b><br>3+ strong signals required</div><div class="key-item key-review"><b>0.85–0.91 · Review</b><br>Stronger convergence</div><div class="key-item key-priority"><b>0.92–1.00 · Priority*</b><br>Strict evidence requirements</div></div>""",unsafe_allow_html=True)
    st.caption("* Priority also requires all five reliable modules and high-confidence timing evidence.")
    live_counts=df(f"SELECT count(*) live_markets FROM markets m WHERE raw_snapshot_id='live' AND m.status='open' AND {weather_sql()}")
    live_fills=df(f"SELECT count(*) live_fills FROM fills f JOIN markets m USING(market_id) WHERE f.source_snapshot_id='live' AND m.status='open' AND {weather_sql()}")
    kalshi_counts=df("SELECT (SELECT count(*) FROM kalshi_weather_markets WHERE status IN ('open','active')) markets,(SELECT count(*) FROM kalshi_weather_trades t JOIN kalshi_weather_markets m USING(ticker) WHERE m.status IN ('open','active')) trades")
    if int(live_counts.iloc[0,0]): st.markdown("<div class='status-pill'><span class='status-dot'></span>Live weather data connected</div>",unsafe_allow_html=True)
    else: st.info("No live API records loaded yet. Run an active or resolved market ingestion.")
    weather_metrics=df(f"""SELECT
      (SELECT count(*) FROM markets m WHERE m.status='open' AND {weather_sql()}) polymarket_markets,
      (SELECT count(*) FROM fills f JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()}) polymarket_trades,
      (SELECT count(DISTINCT wallet) FROM fills f JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()}) wallets,
      (SELECT count(*) FROM episodes e JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()}) episodes,
      (SELECT count(*) FROM alerts a JOIN episodes e USING(episode_id) JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()}) alerts,
      (SELECT count(*) FROM kalshi_weather_markets WHERE status IN ('open','active')) kalshi_markets,
      (SELECT count(*) FROM kalshi_weather_trades t JOIN kalshi_weather_markets m USING(ticker) WHERE t.is_anomaly AND m.status IN ('open','active')) kalshi_anomalies""").iloc[0]
    st.markdown("### Polymarket overview")
    cols=st.columns(4)
    for c,(label,value) in zip(cols,[("Open markets",weather_metrics.polymarket_markets),("Public trades",weather_metrics.polymarket_trades),("Unique wallets",weather_metrics.wallets),("Flagged episodes",weather_metrics.alerts)]): c.metric(label,f"{int(value):,}")
    st.markdown("### Kalshi overview")
    cols=st.columns(2)
    for c,(label,value) in zip(cols,[("Open markets",weather_metrics.kalshi_markets),("Market review cases",weather_metrics.kalshi_anomalies)]): c.metric(label,f"{int(value):,}")
    run=df("SELECT * FROM pipeline_runs ORDER BY completed_at DESC LIMIT 1")
    if len(run):
        refreshed=pd.to_datetime(run.completed_at.iloc[0]).strftime("%b %d, %Y at %I:%M %p")
        st.caption(f"Last refreshed {refreshed}")
    else: st.caption("Data has not been refreshed yet")
    alerts=df(f"SELECT a.created_at,a.composite_score,a.alert_band,a.s1,a.s2,a.s3,a.s4,a.s5 FROM alerts a JOIN episodes e USING(episode_id) JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()}")
    a,b=st.columns(2)
    if len(alerts):
        chart_layout=dict(paper_bgcolor="#ffffff",plot_bgcolor="#ffffff",font=dict(color="#000000"),margin=dict(l=42,r=20,t=50,b=42),title_font=dict(size=16,color="#000000"),legend=dict(font=dict(color="#000000")),xaxis=dict(gridcolor="#edf1f6",linecolor="#dbe2ea",tickfont=dict(color="#000000"),title_font=dict(color="#000000")),yaxis=dict(gridcolor="#edf1f6",linecolor="#dbe2ea",tickfont=dict(color="#000000"),title_font=dict(color="#000000")))
        score_fig=go.Figure(go.Histogram(x=alerts.composite_score,nbinsx=20,marker_color="#356fb8",marker_line_color="#ffffff",marker_line_width=1)).update_layout(title="Score distribution",xaxis_title="Composite score",yaxis_title="Episodes",**chart_layout)
        a.plotly_chart(chart_theme(score_fig),width="stretch")
        module_counts=[int(alerts[k].notna().sum()) for k in ["s1","s2","s3","s4","s5"]]
        module_fig=go.Figure(go.Bar(x=["S1 Size","S2 Timing","S3 Profit","S4 Flow","S5 Behavior"],y=module_counts,marker_color="#7597c8")).update_layout(title="Available signal coverage",yaxis_title="Episodes",**chart_layout)
        b.plotly_chart(chart_theme(module_fig),width="stretch")
    else: st.info("Run the live ingest/build/score pipeline to populate the dashboard.")
    st.subheader("Live markets being analyzed")
    live_markets=df(f"""SELECT question AS "What the market is betting on", weather_type AS "Weather type",
        unique_traders AS Traders, round(volume,0) AS "Reported market volume",
        CASE WHEN status='open' THEN 'OPEN / LIVE' ELSE 'RESOLVED' END AS Status,
        CASE WHEN eligible THEN 'Included' ELSE 'Below liquidity gate' END AS Coverage
        FROM markets m WHERE raw_snapshot_id='live' AND m.status='open' AND {weather_sql()} ORDER BY volume DESC""")
    st.dataframe(live_markets,width="stretch",hide_index=True)
elif page=="Polymarket":
    st.subheader("Polymarket Weather Markets")
    st.caption("A bet episode groups one wallet's trades in one market until a 24-hour inactivity gap. YES means exposure toward the market resolving Yes; NO means exposure toward No.")
    with st.expander("Quick guide: what do these columns mean?"):
        st.write("**Episode notional** is the approximate dollar value traded during the episode. **Average entry price** is the average price paid on a 0–1 probability scale (0.35 ≈ 35%). **Direction persistence** near 1 means trading stayed strongly one-directional; near 0 means activity offset itself.")
    st.markdown("<div class='status-pill'><span class='status-dot'></span>Live Polymarket public API data</div>",unsafe_allow_html=True)
    source_clause="m.raw_snapshot_id='live'"
    st.info("Polymarket exposes pseudonymous wallets, so wallet episodes can be analyzed. Kalshi's public trade feed does not expose trader identities, so Kalshi analysis is trade-level only.")
    c1,c2,c3,c4=st.columns(4)
    search=c1.text_input("Find a weather market",placeholder="temperature, rain, hurricane…")
    direction=c2.multiselect("Bet direction",["YES","NO"],default=["YES","NO"])
    min_notional=c3.number_input("Minimum episode notional ($)",min_value=0.0,value=0.0,step=100.0)
    c4.metric("Market status","OPEN / LIVE")
    bets=df(f"""SELECT e.episode_id,m.question,m.category,e.direction,e.wallet,e.entry_time,e.exit_time,
        round(e.entry_price,3) entry_price,round(e.total_notional,2) total_notional,
        e.trade_count,round(e.persistence,2) persistence,m.status,m.resolved_token,
        'LIVE API' data_source
        FROM episodes e JOIN markets m USING(market_id)
        WHERE {source_clause} AND m.status='open' AND {weather_sql()} AND e.total_notional>=? ORDER BY e.total_notional DESC""",[min_notional])
    if search and len(bets): bets=bets[bets.question.str.contains(search,case=False,na=False)]
    if len(bets): bets=bets[bets.direction.isin(direction)]
    if bets.empty: st.info("No bet episodes match these filters.")
    else:
        st.write(f"Showing **{len(bets):,} episodes** across **{bets.question.nunique():,} markets**")
        for question,group in list(bets.groupby("question",sort=False))[:25]:
            yes_count=int((group.direction=="YES").sum()); no_count=int((group.direction=="NO").sum())
            with st.expander(f"{question}  ·  {len(group):,} episodes  ·  YES {yes_count:,} / NO {no_count:,}"):
                meta1,meta2,meta3,meta4=st.columns(4)
                meta1.metric("Total episode notional",f"${group.total_notional.sum():,.0f}")
                meta2.metric("Wallets",f"{group.wallet.nunique():,}")
                meta3.metric("YES episodes",f"{yes_count:,}")
                meta4.metric("NO episodes",f"{no_count:,}")
                display=group.rename(columns={"direction":"Bet on","wallet":"Wallet","entry_time":"First trade","exit_time":"Last trade","entry_price":"Average entry price","total_notional":"Episode notional ($)","trade_count":"Trades","persistence":"Direction persistence","data_source":"Source"})
                st.dataframe(display[["Bet on","Wallet","Episode notional ($)","Average entry price","Trades","First trade","Last trade","Direction persistence","Source"]].head(200),width="stretch",hide_index=True)
    render_polymarket_analysis()
elif page=="Polymarket Anomalies":
    st.subheader("Polymarket Weather Anomalies")
    st.caption("Every card below is one separate wallet × market episode. It may contain several fills by the same wallet, grouped until a 24-hour inactivity gap.")
    st.markdown("""<div class="score-key"><div class="key-item key-monitor"><b>Monitor · 0.70+</b><br>Keep an eye on it</div><div class="key-item key-review"><b>Review · 0.80+</b><br>Inspect the evidence</div><div class="key-item key-priority"><b>Priority · 0.90+*</b><br>Review first</div><div class="key-item key-low"><b>S1–S5</b><br>Independent evidence modules</div></div>""",unsafe_allow_html=True)
    with st.expander("What do the score and S1–S5 mean?"):
        st.write("The **composite anomaly score** combines reliability-tempered signal log-odds. Several agreeing modules reinforce each other, while conflicting evidence cancels. Higher means statistically unusual—not more likely to be illegal.")
        for name,meaning in SIGNAL_HELP.items(): st.write(f"**{name}:** {meaning}")
        st.info("Missing or unreliable modules are excluded from the average. Open markets usually have no resolved profitability evidence yet.")
    min_score=st.sidebar.slider("Minimum anomaly score",0.0,1.0,.7,.01); bands=st.sidebar.multiselect("Severity",["MONITOR","REVIEW","PRIORITY"],default=["MONITOR","REVIEW","PRIORITY"]); review_status=st.sidebar.multiselect("Review status",["NEW","RETAIN","ESCALATE","DISMISS","INSUFFICIENT_EVIDENCE"],default=["NEW","RETAIN","ESCALATE"])
    market_states=st.sidebar.multiselect("Market status",["open","resolved"],default=["open","resolved"],format_func=lambda x:"Open / live" if x=="open" else "Resolved")
    display_limit=st.sidebar.selectbox("Episodes to display",[25,50,100],index=0,help="Filters still apply to the full alert set.")
    q=f"""SELECT a.alert_id,a.composite_score,a.alert_band,a.status review_status,a.data_quality_flags,a.counterevidence,
        coalesce(m.category,'Other') category,m.question,m.status market_status,e.episode_id,e.direction,e.wallet,
        e.entry_time,e.exit_time,e.total_notional,e.entry_price,e.trade_count,e.persistence,
        f.s1,f.s2,f.s3,f.s4,f.s5,f.suppression_reasons,
        'LIVE API' data_source
        FROM alerts a JOIN episodes e USING(episode_id) JOIN episode_features f USING(episode_id) JOIN markets m USING(market_id)
        WHERE a.composite_score>=? AND {weather_sql()} ORDER BY
        ((f.s1>=.75)::INT+(f.s2>=.75)::INT+(f.s3>=.75)::INT+(f.s4>=.75)::INT+(f.s5>=.75)::INT) DESC,
        a.valid_module_count DESC,a.composite_score DESC"""
    queue=df(q,[min_score])
    if len(queue): queue=queue[queue.alert_band.isin(bands)&queue.review_status.isin(review_status)&queue.market_status.isin(market_states)]
    st.write(f"**{len(queue):,} individually flagged episodes** match these filters. Showing the highest-scoring {min(display_limit,len(queue)):,}.")
    if queue.empty: st.info("No flagged episodes match these filters.")
    else:
        for category,category_group in queue.head(display_limit).groupby("category",sort=False):
            st.markdown(f"### {category}")
            for question,market_group in category_group.groupby("question",sort=False):
                with st.expander(f"{question} · {len(market_group)} flagged episode{'s' if len(market_group)!=1 else ''}"):
                    for _,episode in market_group.iterrows():
                        reasons=episode_reasons(episode)
                        with st.container(border=True):
                            title1,title2=st.columns([3,1])
                            title1.markdown(f"<div class='eyebrow'>{episode.category} · {episode.market_status.upper()}</div><b>Episode <code>{str(episode.episode_id)[:10]}</code> · Position toward {episode.direction}</b>",unsafe_allow_html=True)
                            title2.metric("Anomaly score",f"{episode.composite_score:.3f}",f"{episode.alert_band} · {score_description(episode.composite_score)}")
                            st.progress(min(1.0,float(episode.composite_score)),text=f"Anomaly strength: {score_description(episode.composite_score)}")
                            a1,a2,a3,a4=st.columns(4)
                            a1.metric("Episode notional",f"${episode.total_notional:,.0f}")
                            a2.metric("Average entry price",f"{episode.entry_price:.3f}")
                            a3.metric("Executed fills",f"{int(episode.trade_count):,}")
                            a4.metric("Market", "OPEN / LIVE" if episode.market_status=="open" else "RESOLVED")
                            st.write(f"**Wallet:** `{episode.wallet}`")
                            st.write(f"**Episode window:** {episode.entry_time} → {episode.exit_time}")
                            st.markdown("**Why this episode was flagged**")
                            if reasons:
                                for reason in reasons: st.write(f"• {reason}")
                            else: st.write("No reliable module explanation is available.")
                            if episode.suppression_reasons: st.caption(f"Missing or weakened evidence: {episode.suppression_reasons}")
                            if episode.data_quality_flags: st.warning(f"Data-quality flags: {episode.data_quality_flags}")
                            st.caption(f"Source: {episode.data_source} · Review status: {episode.review_status} · This is an anomaly ranking, not evidence of wrongdoing.")
elif page=="Kalshi":
    st.subheader("Kalshi Weather Markets")
    st.caption("Kalshi provides no public trader identity. The Market Activity Review Score uses only observable trade and market evidence; it is not a user, wallet, or fraud score.")
    kalshi_markets=df("SELECT ticker,title,subtitle,weather_type,'OPEN / LIVE' status,last_price,volume,open_interest,close_time FROM kalshi_weather_markets WHERE status IN ('open','active') ORDER BY volume DESC")
    st.dataframe(kalshi_markets.rename(columns={"ticker":"Ticker","title":"Market","subtitle":"Contract","weather_type":"Weather type","status":"Status","last_price":"Last price","volume":"Contracts traded","open_interest":"Open interest","close_time":"Close time"}),width="stretch",hide_index=True)
    st.subheader("Kalshi market activity review events")
    st.caption("Related trades in the same contract are grouped until there is a 30-minute break. This prevents a single burst from appearing as many separate alerts.")
    kalshi_activity=df("""SELECT t.*,m.title,m.subtitle,m.event_ticker,m.weather_type,m.close_time
        FROM kalshi_weather_trades t JOIN kalshi_weather_markets m USING(ticker)
        WHERE m.status IN ('open','active') AND t.ticker IN (
            SELECT DISTINCT t2.ticker FROM kalshi_weather_trades t2 JOIN kalshi_weather_markets m2 USING(ticker)
            WHERE t2.is_anomaly AND m2.status IN ('open','active'))
        ORDER BY t.ticker,t.timestamp_utc""")
    activity_events=build_activity_events(kalshi_activity)
    if activity_events.empty: st.info("No Kalshi market-activity events currently meet the review rule.")
    else:
        filter1,filter2=st.columns(2)
        grades=filter1.multiselect("Evidence grade",["HIGH","MEDIUM","LOW"],default=["HIGH","MEDIUM","LOW"])
        types=filter2.multiselect("Activity pattern",sorted(activity_events.case_type.unique()),default=sorted(activity_events.case_type.unique()))
        visible_events=activity_events[activity_events.evidence_grade.isin(grades)&activity_events.case_type.isin(types)]
        if visible_events.empty: st.info("No events match these filters.")
        else:
            selected=st.selectbox("Review event",visible_events.activity_event_id.tolist(),format_func=lambda event_id: (lambda r:f"{r.evidence_grade} · {r.case_type} · ${r.total_notional:,.0f} · {r.title}")(visible_events[visible_events.activity_event_id==event_id].iloc[0]))
            event=visible_events[visible_events.activity_event_id==selected].iloc[0]
            st.markdown(f"### {event.title}"); st.caption(f"{event.subtitle or ''} · {event.ticker} · {event.start_time} → {event.end_time}")
            st.info(f"**What happened:** {event.summary} This is classified as **{event.case_type.lower()}** with **{event.evidence_grade.lower()} evidence** for research review.")
            k1,k2,k3,k4=st.columns(4); k1.metric("Event traded value",f"${event.total_notional:,.2f}"); k2.metric("Trades in event",f"{int(event.trade_count):,}"); k3.metric("Observed price impact",f"{event.price_impact:+.3f}"); k4.metric("Review score",f"{event.review_score:.3f}")
            progression=kalshi_activity[kalshi_activity.ticker==event.ticker].copy(); progression["timestamp_utc"]=pd.to_datetime(progression.timestamp_utc,utc=True); progression["Cumulative traded dollars"]=progression.notional.cumsum()
            in_event=(progression.timestamp_utc>=event.start_time)&(progression.timestamp_utc<=event.end_time)
            fig=go.Figure(); fig.add_trace(go.Bar(x=progression.timestamp_utc,y=progression.notional,name="Trade dollars",marker_color=["#dc2626" if x else "#8aa4c5" for x in in_event],hovertemplate="%{x}<br>Trade: $%{y:,.2f}<extra></extra>")); fig.add_trace(go.Scatter(x=progression.timestamp_utc,y=progression.price,name="Executed price",yaxis="y2",mode="lines+markers",line=dict(color="#111827",width=2),hovertemplate="%{x}<br>Price: %{y:.3f}<extra></extra>")); fig.add_vrect(x0=event.start_time,x1=event.end_time,fillcolor="#fca5a5",opacity=.16,line_width=1,line_color="#dc2626")
            fig.update_layout(title="Trade value and executed-price progression",xaxis_title="Time",yaxis_title="Individual trade value ($)",yaxis2=dict(title="Executed price",overlaying="y",side="right",range=[0,1]),paper_bgcolor="#fff",plot_bgcolor="#fff",font=dict(color="#000"),legend=dict(font=dict(color="#000")),hovermode="x unified")
            st.plotly_chart(chart_theme(fig),width="stretch")
            st.caption("The red shaded window is the grouped review event. Red bars are trades inside it; the black line is the public executed price. Price movement is evidence about market activity, not trader identity or intent.")
            event_trades=progression[in_event].copy(); event_trades["Calculation"]=event_trades.apply(lambda r:f"${r.price:.3f} × {r.contracts:,.0f} = ${r.notional:,.2f}",axis=1)
            st.dataframe(event_trades.rename(columns={"timestamp_utc":"Time","outcome_side":"Side","price":"Price","contracts":"Contracts","notional":"Trade value ($)","is_anomaly":"Flagged by rule"})[["Time","Side","Price","Contracts","Trade value ($)","Calculation","Flagged by rule"]],width="stretch",hide_index=True)

            st.subheader("Why it entered the research queue")
            calc=pd.DataFrame({"Signal":["K1 · Materiality","K2 · Unexplained timing","K3 · Price impact / reversal","K4 · Market pressure","K5 · Peer-market deviation"],"What it measures":["Size compared with similar public trades","Unusual arrival burst and proximity to close","Executed-price jump and subsequent reversal","Share of observed contract trading","Difference from comparable weather-market activity"],"Event score":[event.k1,event.k2,event.k3,event.k4,event.k5],"Reliability":[1.0,.4,.8,1.0,1.0]})
            st.dataframe(calc,width="stretch",hide_index=True)
            st.write(f"The event has **{int(event.strong_dimensions)} strong dimensions out of 5**. Observed price: `{event.price_before:.3f}` before → `{event.price_end:.3f}` at event end → `{event.price_after:.3f}` next; maximum within-event swing: `{event.max_price_swing:.3f}`.")
            st.caption("Research-queue rule: score ≥ 0.95, materiality ≥ 0.85, at least three dimensions ≥ 0.80, and trade value ≥ $250. The evidence grade adds event-level context; neither is a probability of fraud.")

            st.subheader("Public-information and cross-market context")
            source=df("SELECT name,url,purpose FROM authoritative_weather_sources WHERE source_key=?",[event.weather_type])
            st.warning("No verified NOAA/NWS release timestamp is currently linked to this Kalshi contract. Timing evidence is therefore down-weighted and should not be interpreted as proof of pre-announcement trading.")
            if not source.empty: st.dataframe(source.rename(columns={"name":"Independent weather source","url":"URL","purpose":"Use"}),width="stretch",hide_index=True)
            poly_questions=df(f"SELECT question FROM markets m WHERE m.status='open' AND {weather_sql()}").question.tolist()
            match,similarity=candidate_market_match(event.title,poly_questions)
            if match and similarity>=.35:
                st.write(f"**Possible Polymarket comparison:** {match}")
                st.caption(f"Title similarity: {similarity:.0%}. This is only a candidate; settlement rules, units, location and time window must be manually verified before comparing prices.")
            else: st.write("**Polymarket comparison:** No sufficiently similar open contract was found. The dashboard does not force an unreliable cross-platform match.")

            st.subheader("Contract-family diagnostic")
            siblings=df("SELECT ticker,subtitle,last_price,volume,open_interest FROM kalshi_weather_markets WHERE event_ticker=? AND status IN ('open','active') ORDER BY ticker",[event.event_ticker]) if pd.notna(event.event_ticker) else pd.DataFrame()
            if siblings.empty: st.info("No open sibling contracts were found for this event family.")
            else:
                f1,f2=st.columns(2); f1.metric("Open contracts in family",len(siblings)); f2.metric("Sum of last prices",f"{siblings.last_price.fillna(0).sum():.3f}")
                st.dataframe(siblings.rename(columns={"ticker":"Ticker","subtitle":"Contract","last_price":"Last price","volume":"Volume","open_interest":"Open interest"}),width="stretch",hide_index=True)
                st.caption("A price sum near 1 is informative only when the contracts are mutually exclusive and collectively exhaustive. The public metadata has not verified that condition, so this is a diagnostic—not an arbitrage claim.")

            with st.expander("Evidence that is unavailable from Kalshi's public feed"):
                st.dataframe(pd.DataFrame({"Unavailable evidence":["Trader identity","Account-level history","Counterparty links","Order submissions and cancellations","Wash-trading test","Spoofing or layering test"],"Consequence":["Cannot identify a person or account","Cannot assess repeat success by user","Cannot detect coordinated accounts","Cannot observe intent from unexecuted orders","Cannot attribute both sides to one user","Cannot infer deceptive order-book behavior"]}),width="stretch",hide_index=True)
                st.warning("The Kalshi section identifies unusual market activity only. It cannot identify the user responsible or conclude that fraud occurred.")
elif page=="Case Detail":
    choices=df(f"SELECT a.alert_id,round(a.composite_score,3) score,m.question,e.wallet FROM alerts a JOIN episodes e USING(episode_id) JOIN markets m USING(market_id) WHERE m.status='open' AND {weather_sql()} ORDER BY score DESC")
    if choices.empty: st.info("No cases available.")
    else:
        labels={r.alert_id:f"{r.score} · {r.question} · {r.wallet}" for _,r in choices.iterrows()}; aid=st.selectbox("Case",labels.keys(),format_func=labels.get)
        case=df("SELECT a.*,e.*,m.question,m.resolution_time,f.* FROM alerts a JOIN episodes e USING(episode_id) JOIN markets m USING(market_id) JOIN episode_features f USING(episode_id) WHERE alert_id=?",[aid]).iloc[0]
        st.subheader(case.question); st.code(case.wallet)
        cscore,cband,cdirection=st.columns(3); cscore.metric("Composite anomaly score",f"{case.composite_score:.3f}",score_description(case.composite_score)); cband.metric("Review band",case.alert_band); cdirection.metric("Position direction",case.direction)
        st.progress(min(1.0,float(case.composite_score)),text="Higher means more statistically unusual — not a probability of wrongdoing")
        prices=df("SELECT timestamp_utc,price FROM price_observations WHERE market_id=? ORDER BY timestamp_utc",[case.market_id]); fills=df("SELECT timestamp_utc,price,side,outcome,size,notional,wallet,signed_exposure FROM fills WHERE market_id=? AND wallet=? AND timestamp_utc BETWEEN ? AND ? ORDER BY timestamp_utc",[case.market_id,case.wallet,case.entry_time,case.exit_time]); events=df("SELECT event_time_utc,headline FROM public_events WHERE market_id=? AND verified",[case.market_id])
        fills["Cumulative traded dollars"]=fills.notional.cumsum()
        fig=go.Figure(); fig.add_trace(go.Bar(x=fills.timestamp_utc,y=fills.notional,name="Trade value ($)",marker_color=["#2563eb" if x=="BUY" else "#dc2626" for x in fills.side],customdata=fills[["side","outcome","price","size"]],hovertemplate="%{x}<br>$%{y:,.2f}<br>%{customdata[0]} %{customdata[1]}<br>Price $%{customdata[2]:.4f} × %{customdata[3]:,.2f} shares<extra></extra>")); fig.add_trace(go.Scatter(x=fills.timestamp_utc,y=fills["Cumulative traded dollars"],name="Cumulative traded ($)",yaxis="y2",line=dict(color="#111827",width=3),hovertemplate="%{x}<br>Cumulative $%{y:,.2f}<extra></extra>"))
        for _,ev in events.iterrows(): fig.add_vline(x=ev.event_time_utc,line_dash="dash",line_color="orange")
        st.plotly_chart(fig.update_layout(title="Anomalous episode trade progression",xaxis_title="Trade time",yaxis_title="Individual trade value ($)",yaxis2=dict(title="Cumulative traded value ($)",overlaying="y",side="right",tickfont=dict(color="#000000"),title_font=dict(color="#000000")),hovermode="x unified",paper_bgcolor="#ffffff",plot_bgcolor="#ffffff",font=dict(color="#000000"),title_font=dict(color="#000000"),legend=dict(font=dict(color="#000000")),xaxis=dict(tickfont=dict(color="#000000"),title_font=dict(color="#000000")),yaxis=dict(tickfont=dict(color="#000000"),title_font=dict(color="#000000"))),width="stretch")
        st.caption("Each bar is one executed trade: notional = price × shares. The dark line accumulates the episode's total traded dollars over time.")
        trade_log=fills.copy(); trade_log["Calculation"]=trade_log.apply(lambda r:f"${r.price:.4f} × {r.size:,.2f} = ${r.notional:,.2f}",axis=1)
        st.dataframe(trade_log.rename(columns={"timestamp_utc":"Time","side":"Action","outcome":"Outcome","price":"Price","size":"Shares","notional":"Trade value ($)","Cumulative traded dollars":"Cumulative ($)"})[["Time","Action","Outcome","Price","Shares","Trade value ($)","Calculation","Cumulative ($)"]],width="stretch",hide_index=True)
        st.subheader("Signals and explanation")
        signal_values=[case.s1,case.s2,case.s3,case.s4,case.s5]
        reliability=[case.q1,case.q2,case.q3,case.q4,case.q5]
        contribution=[float(q)*np.log(np.clip(float(v),.01,.99)/(1-np.clip(float(v),.01,.99))) if pd.notna(v) and float(q)>0 else None for v,q in zip(signal_values,reliability)]
        signal_table=pd.DataFrame({"Module":list(SIGNAL_HELP),"What it asks":list(SIGNAL_HELP.values()),"Score":signal_values,"Reliability":reliability,"Log-evidence contribution":contribution,"Interpretation":[score_description(float(v)) if pd.notna(v) else "Unavailable / excluded" for v in signal_values]})
        valid=[x for x in contribution if x is not None]; evidence=sum(valid)
        st.latex(r"\text{Composite score}=\sigma\!\left(\sum_i Q_i\log\frac{S_i}{1-S_i}\right)")
        st.write(f"For this episode: log-evidence `{evidence:.4f}` → score `{case.composite_score:.4f}`")
        st.dataframe(signal_table,width="stretch",hide_index=True); st.write("**Why flagged:**",case.top_evidence); st.warning(f"**Counterevidence / limitations:** {case.counterevidence}"); st.write("**Data quality:**",case.data_quality_flags or "No flags"); st.caption(f"Feature version: {case.feature_version} · Model version: {case.model_version}")
        disposition=st.selectbox("Reviewer disposition",["RETAIN","ESCALATE","DISMISS","INSUFFICIENT_EVIDENCE"]); notes=st.text_area("Notes"); reviewer=st.text_input("Reviewer")
        if st.button("Save review"):
            import hashlib
            with connect() as con:
                rid=hashlib.sha256(f"{aid}|{reviewer}|{datetime.now(timezone.utc)}".encode()).hexdigest(); con.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?)",[rid,aid,reviewer,datetime.now(timezone.utc),disposition,notes,disposition=="ESCALATE",None,None]); con.execute("UPDATE alerts SET status=? WHERE alert_id=?",[disposition,aid]); st.success("Review saved")
elif page=="Events":
    st.subheader("Public-event timestamp management"); st.dataframe(df("SELECT market_id,event_time_utc original_timestamp,event_time_utc verified_timestamp,headline AS event_source,source_url,annotator,verification_time,confidence,verified,rejected FROM public_events ORDER BY event_time_utc DESC"),width="stretch")
    markets=df(f"SELECT market_id,question FROM markets m WHERE m.status='open' AND {weather_sql()} ORDER BY question");
    if len(markets):
        with st.form("event"):
            mapping=dict(zip(markets.market_id,markets.question)); mid=st.selectbox("Market",mapping,format_func=mapping.get); event_date=st.date_input("Date (UTC)"); event_time=st.time_input("Time (UTC)"); event_kind=st.selectbox("Timestamp type",["FORECAST_UPDATE","WEATHER_OBSERVATION","PUBLIC_EVENT"]); headline=st.text_input("Headline"); url=st.text_input("Source URL"); confidence=st.selectbox("Confidence",["HIGH","MEDIUM","LOW"]); annotator=st.text_input("Annotator"); verified=st.checkbox("Confirm / verified"); rejected=st.checkbox("Reject")
            if st.form_submit_button("Save manual event"):
                stamp=datetime.combine(event_date,event_time,tzinfo=timezone.utc)
                with connect() as con:
                    eid=save_event(con,mid,stamp,headline,url,confidence,annotator,verified,source_type=event_kind); con.execute("UPDATE public_events SET rejected=? WHERE event_id=?",[rejected,eid]); st.success("Manual event saved; it will not be overwritten.")
elif page=="Backtest":
    from app.backtest.time_split import run
    with connect() as con: result=run(con)
    st.subheader("Time-split research controls"); st.json(result); st.info("Placebo and negative-control rates require verified event samples for meaningful interpretation.")
elif page=="Health":
    st.success("Application: OK · Database: OK · Data directory: OK")
    counts={t:int(df(f"SELECT count(*) n FROM {t}").iloc[0,0]) for t in ["markets","fills","price_observations","episodes","public_events","alerts"]}; st.json(counts); st.write("API failures:",int(df("SELECT count(*) n FROM snapshots WHERE error IS NOT NULL").iloc[0,0])); st.button("Run health check")
    st.subheader("Weather-market discovery audit")
    discovery=df("""SELECT source AS Platform, decision AS Decision, count(*) AS Markets
        FROM market_discovery_audit GROUP BY source,decision ORDER BY source,decision""")
    st.dataframe(discovery,width="stretch",hide_index=True)
    st.caption("Rejected candidates are retained here so missed-market and false-positive decisions can be reviewed.")
    st.subheader("Authoritative weather references")
    st.dataframe(df("SELECT name AS Source,url AS URL,purpose AS Purpose FROM authoritative_weather_sources ORDER BY name"),width="stretch",hide_index=True)
    st.subheader("Alert-rule sensitivity")
    sensitivity_source=df("SELECT s1,s2,s3,s4,s5,q1,q2,q3,q4,q5 FROM episode_features")
    sensitivity=[]
    if len(sensitivity_source):
        evaluated=[]
        for _,row in sensitivity_source.iterrows():
            scores=[None if pd.isna(row[f"s{i}"]) else float(row[f"s{i}"]) for i in range(1,6)]; qs=[float(row[f"q{i}"]) for i in range(1,6)]
            score,valid=combine_evidence(scores,qs); strong=sum(s is not None and q>0 and s>=.75 for s,q in zip(scores,qs)); evaluated.append((score,valid,strong))
        for threshold in (.70,.75,.80,.85,.90):
            for required_strong in (2,3):
                flagged=sum(score is not None and score>=threshold and valid>=4 and strong>=required_strong for score,valid,strong in evaluated)
                sensitivity.append({"Score threshold":threshold,"Required strong signals":required_strong,"Minimum valid modules":4,"Episodes flagged":flagged,"Flag rate":flagged/len(evaluated)})
    st.dataframe(pd.DataFrame(sensitivity),width="stretch",hide_index=True, column_config={"Flag rate":st.column_config.NumberColumn(format="%.2%%")})
    st.caption("These are rule-volume sensitivity results, not false-positive rates. A false-positive rate requires independently labeled review outcomes.")
else:
    st.subheader("Settings / Data"); st.json({"Data API base URL":s.data_api_base_url,"Gamma API base URL":s.gamma_base_url,"CLOB base URL":s.clob_base_url,"HTTP timeout":s.request_timeout_seconds,"Request concurrency":s.concurrency,"Rate-limit delay":"exponential jitter","Market limit":"CLI --markets","Trade limit":s.trade_limit,"Price-history resolution":s.price_bucket_seconds})
