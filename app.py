import base64
import json
import uuid
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Manufacturing Profit Challenge", page_icon="🏆", layout="wide")

# -----------------------------------------------------------------------------
# MODEL CONFIGURATION
# All effects are incremental by ACTIVE month and carry forward in process state.
# -----------------------------------------------------------------------------
BASELINE = {
    "productivity": 80.0,
    "quality": 0.75,
    "manufacturing_cost": 30.0,
    "selling_price": 50.0,
    "capital_budget": 1500.0,
}

ACTIVITIES = {
    "Parallel Equipment Installation (Line Balancing)": {
        "icon": "🏭",
        "capital_cost": 750.0,
        "productivity_increment": [5.0, 0.0, 0.0, 0.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [1.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "+5 products/month in the activation month; the improved level then remains constant.",
            "Quality": "No change in the activation month or later active months.",
            "Manufacturing Cost": "Decreases by 1 per product in the activation month; the reduced level then remains constant.",
        },
    },
    "Changeover Time Optimization (SMED)": {
        "icon": "⏱️",
        "capital_cost": 375.0,
        "productivity_increment": [5.0, 1.0, 1.0, 1.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [2.0, 1.0, 1.0, 1.0],
        "effect_lines": {
            "Productivity": "+5 products/month in Active M1, then +1 product/month in each later active month.",
            "Quality": "No change in any active month.",
            "Manufacturing Cost": "Decreases by 2 per product in Active M1, then by 1 per product in each later active month.",
        },
    },
    "Run Beyond Equipment Rated Capacity": {
        "icon": "⚙️",
        "capital_cost": 150.0,
        "productivity_increment": [1.0, 0.0, 0.0, 0.0],
        "quality_increment": [-0.05, -0.05, -0.05, -0.05],
        "cost_reduction_increment": [0.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "+1 product/month in the activation month; no later productivity increment.",
            "Quality": "Decreases by 5 percentage points in every active month due to continued operation beyond rated capacity.",
            "Manufacturing Cost": "No manufacturing-cost reduction in any active month.",
        },
    },
    "Preventive Maintenance (CLTI)": {
        "icon": "🔧",
        "capital_cost": 300.0,
        "productivity_increment": [1.0, 1.0, 1.0, 1.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [0.0, 1.0, 1.0, 1.0],
        "effect_lines": {
            "Productivity": "+1 product/month in every active month.",
            "Quality": "No change in any active month.",
            "Manufacturing Cost": "No change in Active M1, then decreases by 1 per product in each later active month.",
        },
    },
    "Statistical Process Control": {
        "icon": "📊",
        "capital_cost": 300.0,
        "productivity_increment": [0.0, 0.0, 0.0, 0.0],
        "quality_increment": [0.03, 0.03, 0.03, 0.03],
        "cost_reduction_increment": [0.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "No change in any active month.",
            "Quality": "+3 percentage points in every active month.",
            "Manufacturing Cost": "No change in any active month.",
        },
    },
    "Operator Training & Performance Management": {
        "icon": "👷",
        "capital_cost": 375.0,
        "productivity_increment": [0.0, 1.0, 1.0, 1.0],
        "quality_increment": [0.00, 0.01, 0.01, 0.01],
        "cost_reduction_increment": [0.0, 1.0, 1.0, 1.0],
        "effect_lines": {
            "Productivity": "No change in Active M1, then +1 product/month in each later active month.",
            "Quality": "No change in Active M1, then +1 percentage point in each later active month.",
            "Manufacturing Cost": "No change in Active M1, then decreases by 1 per product in each later active month.",
        },
    },
}

LEADERBOARD_FILE = "data/leaderboard.json"

# -----------------------------------------------------------------------------
# STYLE
# -----------------------------------------------------------------------------
st.markdown("""
<style>
.stApp{background:#f5fbf7}.block-container{max-width:1380px;padding-top:1rem;padding-bottom:3rem}
.hero{padding:1.5rem 1.8rem;border-radius:22px;background:linear-gradient(120deg,#123d29,#15803d);color:white;margin-bottom:1rem}.hero h1{margin:0}.hero p{margin:.4rem 0 0}
.kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:1rem 0}.kpi{min-width:0;background:#f1faf4;border:1px solid #cde2d2;border-radius:18px;padding:1rem}.kl{font-size:.9rem;color:#234535}.kv{font-size:clamp(1.25rem,2.1vw,2.05rem);line-height:1.05;margin-top:.5rem;overflow-wrap:anywhere}.ku{display:block;font-size:.72rem;color:#526b5e;margin-top:.35rem}
.summary{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden;margin:1rem 0}.summary th{background:#166534;color:white;padding:.65rem;text-align:center}.summary td{border:1px solid #d8e5dc;padding:.58rem;text-align:center}.summary td:first-child{font-weight:750;text-align:left}.summary tr:last-child td{background:#ecfdf5;font-weight:800}
.diag{padding:1rem;border:1px solid #93c5fd;background:#eff6ff;border-radius:16px;line-height:1.65;margin:1rem 0}.steps{display:flex;gap:8px;justify-content:center;margin:1rem 0}.step{padding:.7rem 1.2rem;border-radius:12px;background:#e2e8f0;font-weight:700}.done{background:#bbf7d0}.current{background:#15803d;color:white}
.activity{background:white;border:1px solid #dae7de;border-radius:18px;padding:1rem;margin-bottom:12px}.unavailable{opacity:.45}.activity h3{margin:.2rem 0}.effect{width:100%;border-collapse:collapse;font-size:.83rem}.effect td{padding:.55rem;border-bottom:1px solid #e1e8e3;vertical-align:top}.effect td:first-child{width:32%;font-weight:750;color:#14532d;background:#f8fafc}.capital{padding:.5rem;background:#ecfdf5;color:#166534;font-weight:800;border-radius:9px;margin-top:.6rem}
@media(max-width:950px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.kpi-grid{grid-template-columns:repeat(2,1fr)}.steps{flex-wrap:wrap}}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SHARED LEADERBOARD VIA GITHUB
# -----------------------------------------------------------------------------
def github_configured():
    return all(str(st.secrets.get(k, "")).strip() for k in ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"])

def github_headers():
    return {"Authorization":f"Bearer {st.secrets['GITHUB_TOKEN']}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Cache-Control":"no-cache"}

def github_url():
    return f"https://api.github.com/repos/{st.secrets['GITHUB_OWNER']}/{st.secrets['GITHUB_REPO']}/contents/{LEADERBOARD_FILE}"

def github_branch():
    return st.secrets.get("GITHUB_BRANCH", "main")

def read_board():
    r=requests.get(github_url(),headers=github_headers(),params={"ref":github_branch(),"_":datetime.now().timestamp()},timeout=30)
    if r.status_code==404:return {},None
    r.raise_for_status();payload=r.json();raw=base64.b64decode(payload["content"]).decode("utf-8").strip()
    data=json.loads(raw or "{}")
    if not isinstance(data,dict):raise RuntimeError("data/leaderboard.json must contain {} or a JSON object.")
    return data,payload["sha"]

def save_shared(record):
    sid=str(record["Session ID"]);local=st.session_state.get("local_players",{});local[sid]=record;st.session_state.local_players=local
    if not github_configured():return
    for _ in range(8):
        rows,sha=read_board();rows[sid]=record
        body={"message":f"Update leaderboard {record['Team Name']}","content":base64.b64encode(json.dumps(rows,ensure_ascii=False,indent=2).encode()).decode(),"branch":github_branch()}
        if sha:body["sha"]=sha
        r=requests.put(github_url(),headers=github_headers(),json=body,timeout=30)
        if r.status_code in (200,201):return
        if r.status_code not in (409,422):r.raise_for_status()
    raise RuntimeError("Leaderboard was busy. Please retry once.")

def all_players():
    rows={}
    if github_configured():rows,_=read_board()
    for key,value in st.session_state.get("local_players",{}).items():rows[key]=value
    return list(rows.values())

# -----------------------------------------------------------------------------
# SIMULATION
# -----------------------------------------------------------------------------
def initial_state():
    return {"month":0,"capital_budget":1500.0,"selections":{},"productivity":80.0,"quality":.75,"manufacturing_cost":30.0,"cumulative_profit":0.0,"history":[]}

def calculate_month(state,month,new_activity=None):
    p,q,c=state["productivity"],state["quality"],state["manufacturing_cost"]
    active=dict(state["selections"])
    if new_activity:active[month]=new_activity
    ages=[];effects=[]
    for activation,name in sorted(active.items()):
        index=month-activation;a=ACTIVITIES[name]
        dp=a["productivity_increment"][index];dq=a["quality_increment"][index];dc=a["cost_reduction_increment"][index]
        p+=dp;q+=dq;c-=dc
        ages.append(f"{name}: Active M{index+1}")
        effects.append(f"{name}: productivity {dp:+.1f} products/month, quality {dq*100:+.1f} pp, cost {-dc:+.1f}/product")
    q=max(0,min(1,q));c=max(0,c);capital=ACTIVITIES[new_activity]["capital_cost"] if new_activity else 0.0
    good=p*q;landed=(p*c+capital)/p if p else 0.0;profit=good*50-p*c-capital
    return {"month":month,"productivity":p,"quality":q,"manufacturing_cost":c,"capital_cost":capital,"landed_cost":landed,"monthly_profit":profit,"ages":" | ".join(ages),"effects":" | ".join(effects)}

def player_record(state,label):
    latest=state["history"][-1] if state["history"] else None
    return {"Session ID":st.session_state.session_id,"Team Name":st.session_state.team_name,"Team Members":st.session_state.team_members,"Month":state["month"],"Selected Activity":label,"Cumulative Profit":state["cumulative_profit"],"Capital Budget Remaining":state["capital_budget"],"Updated At":datetime.now().isoformat(timespec="microseconds"),"Productivity":latest["productivity"] if latest else 80,"Quality %":latest["quality"]*100 if latest else 75,"Manufacturing Cost":latest["manufacturing_cost"] if latest else 30}

def run_month(no_new=False):
    state=st.session_state.state.copy();state["history"]=list(state["history"]);state["selections"]=dict(state["selections"])
    month=state["month"]+1;selected=None if no_new else st.session_state.get("selected_activity")
    if not selected and not no_new:st.error("Select one activity.");return
    capital=ACTIVITIES[selected]["capital_cost"] if selected else 0.0
    if capital>state["capital_budget"]:st.error("Insufficient capital budget.");return
    result=calculate_month(state,month,selected);result["selected"]=selected or "No New Activity - Existing Effects Continue"
    state["month"]=month;state["capital_budget"]-=capital
    if selected:state["selections"][month]=selected
    state["productivity"]=result["productivity"];state["quality"]=result["quality"];state["manufacturing_cost"]=result["manufacturing_cost"]
    state["cumulative_profit"]+=result["monthly_profit"];result["cumulative_profit"]=state["cumulative_profit"];state["history"].append(result);st.session_state.state=state
    try:save_shared(player_record(state,result["selected"]))
    except Exception as error:st.warning(f"Leaderboard update failed: {error}")
    st.rerun()

def continue_existing():run_month(True)

# -----------------------------------------------------------------------------
# UI HELPERS
# -----------------------------------------------------------------------------
def hero():
    st.markdown("<div class='hero'><h1>🏆 Four-Month Profit Optimization Challenge</h1><p>Effects are applied by active month and remain accumulated.</p></div>",unsafe_allow_html=True)

def history_table(state):
    baseline_profit=80*.75*50-80*30
    rows=[{"Period":"Baseline","Productivity":"80.0 products/month","Quality":"75.0%","Manufacturing Cost":"30.0 /product","Landed Cost":"30.00 /product","Monthly Profit":f"{baseline_profit:,.1f}","Cumulative Profit":"0.0"}]
    for h in state["history"]:
        rows.append({"Period":f"Month {h['month']}","Productivity":f"{h['productivity']:.1f} products/month","Quality":f"{h['quality']:.1%}","Manufacturing Cost":f"{h['manufacturing_cost']:.1f} /product","Landed Cost":f"{h['landed_cost']:.2f} /product","Monthly Profit":f"{h['monthly_profit']:,.1f}","Cumulative Profit":f"{h['cumulative_profit']:,.1f}"})
    for month in range(state["month"]+1,5):
        rows.append({"Period":f"Month {month}","Productivity":"-","Quality":"-","Manufacturing Cost":"-","Landed Cost":"-","Monthly Profit":"-","Cumulative Profit":"-"})
    rows.append({"Period":"Cumulative","Productivity":"-","Quality":"-","Manufacturing Cost":"-","Landed Cost":"-","Monthly Profit":"-","Cumulative Profit":f"{state['cumulative_profit']:,.1f}"})
    st.markdown(pd.DataFrame(rows).to_html(index=False,escape=False,classes="summary"),unsafe_allow_html=True)

def performance_graph(state):
    baseline_profit=80*.75*50-80*30
    periods=["Baseline"]+[f"Month {h['month']}" for h in state["history"]]
    monthly=[baseline_profit]+[h["monthly_profit"] for h in state["history"]]
    cumulative=[0.0]+[h["cumulative_profit"] for h in state["history"]]
    p=[80.0]+[h["productivity"] for h in state["history"]];q=[75.0]+[h["quality"]*100 for h in state["history"]];c=[30.0]+[h["manufacturing_cost"] for h in state["history"]]
    fig=go.Figure();fig.add_bar(x=periods,y=monthly,name="Monthly Profit",marker_color="#15803d",text=[f"{v:,.1f}" for v in monthly],textposition="outside");fig.add_scatter(x=periods,y=cumulative,name="Cumulative Profit",mode="lines+markers+text",text=[f"{v:,.1f}" for v in cumulative],textposition="top center",line=dict(color="#f59e0b",width=3));fig.update_layout(title="Monthly and Cumulative Profit Trend",height=420,hovermode="x unified",legend=dict(orientation="h",y=1.08));st.plotly_chart(fig,use_container_width=True)
    fig2=go.Figure();fig2.add_scatter(x=periods,y=p,name="Productivity (products/month)",mode="lines+markers");fig2.add_scatter(x=periods,y=q,name="Quality (%)",mode="lines+markers");fig2.add_scatter(x=periods,y=c,name="Manufacturing Cost (cost/product)",mode="lines+markers");fig2.update_layout(title="Operational KPI Trend",height=420,hovermode="x unified",legend=dict(orientation="h",y=1.08));st.plotly_chart(fig2,use_container_width=True)

def activity_card(name,a,unavailable):
    cls="activity unavailable" if unavailable else "activity";lines=a["effect_lines"]
    return f"<div class='{cls}'><div style='font-size:2rem'>{a['icon']}</div><h3>{name}</h3><table class='effect'><tr><td>Productivity<br><small>products/month</small></td><td>{lines['Productivity']}</td></tr><tr><td>Quality<br><small>percentage points</small></td><td>{lines['Quality']}</td></tr><tr><td>Manufacturing Cost<br><small>cost/product</small></td><td>{lines['Manufacturing Cost']}</td></tr></table><div class='capital'>Capital Cost: {a['capital_cost']:,.0f}</div></div>"

def leaderboard():
    a,b=st.columns([5,1]);a.subheader("🏅 Live Shared Leaderboard")
    if b.button("Refresh ↻",use_container_width=True):st.rerun()
    if not github_configured():st.error("Shared storage is not connected. Configure GitHub secrets.")
    try:rows=all_players()
    except Exception as error:st.warning(f"Leaderboard refresh failed: {error}");rows=list(st.session_state.get("local_players",{}).values())
    if not rows:st.info("Registered players will appear here.");return
    frame=pd.DataFrame(rows);frame["Cumulative Profit"]=pd.to_numeric(frame["Cumulative Profit"],errors="coerce").fillna(0);frame=frame.sort_values(["Cumulative Profit","Month"],ascending=[False,False]).reset_index(drop=True);frame.insert(0,"Rank",range(1,len(frame)+1));st.dataframe(frame[["Rank","Team Name","Team Members","Month","Selected Activity","Cumulative Profit","Capital Budget Remaining"]],use_container_width=True,hide_index=True)

# -----------------------------------------------------------------------------
# PAGES
# -----------------------------------------------------------------------------
def registration_page():
    hero();_,center,_=st.columns([1,1.4,1])
    with center:
        with st.form("registration"):
            st.subheader("Register Your Team");team=st.text_input("Team Name *");members=st.text_area("Team Members *");submitted=st.form_submit_button("Start Challenge",use_container_width=True)
        if submitted:
            if not team.strip() or not members.strip():st.error("Enter Team Name and Team Members.")
            else:
                st.session_state.update(registered=True,session_id=str(uuid.uuid4()),team_name=team.strip(),team_members=members.strip(),state=initial_state(),local_players={})
                try:save_shared(player_record(st.session_state.state,"Registered - Not Started"))
                except Exception as error:st.warning(f"Registration saved locally; shared save failed: {error}")
                st.rerun()

def dashboard_page():
    hero();state=st.session_state.state
    with st.sidebar:
        st.success(st.session_state.team_name);st.write(st.session_state.team_members);st.metric("Month",f"{state['month']} / 4");st.metric("Capital Budget",f"{state['capital_budget']:,.0f}");st.metric("Cumulative Profit",f"{state['cumulative_profit']:,.1f}")
        if st.button("Restart"):st.session_state.clear();st.rerun()
    if state["history"]:
        h=state["history"][-1]
        st.markdown(f"<div class='kpi-grid'><div class='kpi'><div class='kl'>Productivity</div><div class='kv'>{h['productivity']:.1f}<span class='ku'>products/month</span></div></div><div class='kpi'><div class='kl'>Quality</div><div class='kv'>{h['quality']:.1%}<span class='ku'>good products</span></div></div><div class='kpi'><div class='kl'>Manufacturing Cost</div><div class='kv'>{h['manufacturing_cost']:.1f}<span class='ku'>cost/product</span></div></div><div class='kpi'><div class='kl'>Landed Cost</div><div class='kv'>{h['landed_cost']:.2f}<span class='ku'>cost/product</span></div></div><div class='kpi'><div class='kl'>Monthly Profit</div><div class='kv'>{h['monthly_profit']:,.1f}<span class='ku'>per month</span></div></div></div>",unsafe_allow_html=True)
    st.subheader("Month-wise Performance Summary");history_table(state)
    st.subheader("Performance Graphs");performance_graph(state)
    if state["history"]:
        h=state["history"][-1];st.markdown(f"<div class='diag'><b>Active activity age:</b> {h['ages']}<br><b>Increment applied this month:</b> {h['effects']}</div>",unsafe_allow_html=True)
    st.markdown("<div class='steps'>"+"".join(f"<div class='step {'done' if m<=state['month'] else 'current' if m==state['month']+1 else ''}'>Month {m}</div>" for m in range(1,5))+"</div>",unsafe_allow_html=True)
    if state["month"]<4:
        month=state["month"]+1;used=set(state["selections"].values());available=[name for name,a in ACTIVITIES.items() if name not in used and a["capital_cost"]<=state["capital_budget"]];cols=st.columns(2)
        for i,(name,a) in enumerate(ACTIVITIES.items()):
            with cols[i%2]:st.markdown(activity_card(name,a,name in used or a["capital_cost"]>state["capital_budget"]),unsafe_allow_html=True)
        if available:
            selected=st.selectbox(f"Month {month}: Select one activity",available,index=None);st.session_state.selected_activity=selected;st.button(f"Run Month {month}",type="primary",use_container_width=True,disabled=not selected,on_click=run_month)
        else:
            st.info("No activity is affordable. Existing effects can continue.");st.button(f"Continue to Month {month}",type="primary",use_container_width=True,on_click=continue_existing)
    else:st.success(f"Simulation complete. Cumulative profit: {state['cumulative_profit']:,.1f}")
    leaderboard()

if st.session_state.get("registered"):dashboard_page()
else:registration_page()
