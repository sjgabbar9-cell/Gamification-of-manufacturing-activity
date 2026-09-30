import base64
import io
import itertools
import uuid
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(
    page_title="Four-Month Profit Optimization Challenge",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# MODEL INPUTS
# Values below are incremental contributions against the Month 0 baseline.
# Once selected, an activity remains active and follows M1-M4 maturity values.
# =============================================================================
BASELINE = {
    "productivity": 80.0,
    "quality": 0.75,
    "manufacturing_cost": 30.0,
    "selling_price": 50.0,
    "capital_budget": 1500.0,
}

ACTIVITIES = {
    "Parallel Line Installation": {
        "icon": "🏭",
        "capital_cost": 750.0,
        "productivity_delta": [10.0, 10.0, 10.0, 10.0],
        "quality_delta": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction": [3.0, 3.0, 3.0, 3.0],
        "effect_lines": {
            "Productivity": "Increases by 10 tiles/day in Month 1 and remains at the same improved level through Month 4.",
            "Quality": "No change; quality remains at the 75% baseline through Month 4.",
            "Manufacturing Cost": "Decreases by 3 per tile in Month 1 and remains at the same reduced level through Month 4.",
        },
    },
    "Changeover Time Optimization (SMED)": {
        "icon": "⏱️",
        "capital_cost": 375.0,
        "productivity_delta": [10.0, 10.0, 10.0, 10.0],
        "quality_delta": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction": [3.0, 3.0, 3.0, 3.0],
        "effect_lines": {
            "Productivity": "Increases by 10 tiles/day in Month 1 and remains at the same improved level through Month 4.",
            "Quality": "No change; quality remains at the 75% baseline through Month 4.",
            "Manufacturing Cost": "Decreases by 3 per tile in Month 1 and remains at the same reduced level through Month 4.",
        },
    },
    "Increase Speed of Bottleneck": {
        "icon": "⚙️",
        "capital_cost": 150.0,
        "productivity_delta": [10.0, 10.0, 10.0, 10.0],
        "quality_delta": [-0.01, -0.01, -0.01, -0.01],
        "cost_reduction": [3.0, 3.0, 3.0, 3.0],
        "effect_lines": {
            "Productivity": "Increases by 10 tiles/day in Month 1 and remains at the same improved level through Month 4.",
            "Quality": "Decreases by 1 percentage point in Month 1 and remains at that level through Month 4.",
            "Manufacturing Cost": "Decreases by 3 per tile in Month 1 and remains at the same reduced level through Month 4.",
        },
    },
    "Preventive Maintenance (CLTI)": {
        "icon": "🔧",
        "capital_cost": 300.0,
        "productivity_delta": [1.0, 2.0, 3.0, 4.0],
        "quality_delta": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction": [0.0, 1.0, 2.0, 3.0],
        "effect_lines": {
            "Productivity": "Increases by 1 tile/day in every active month, reaching a 4 tiles/day increase by Month 4.",
            "Quality": "No change; quality remains at the 75% baseline through Month 4.",
            "Manufacturing Cost": "No change in Month 1, then decreases by 1 per tile in each subsequent active month.",
        },
    },
    "Statistical Process Control": {
        "icon": "📊",
        "capital_cost": 300.0,
        "productivity_delta": [0.0, 0.0, 0.0, 0.0],
        "quality_delta": [0.02, 0.04, 0.06, 0.08],
        "cost_reduction": [0.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "No change; productivity remains at the current level through Month 4.",
            "Quality": "Increases by 2 percentage points in every active month, reaching an 8 percentage-point increase by Month 4.",
            "Manufacturing Cost": "No change; manufacturing cost remains at the current level through Month 4.",
        },
    },
    "Operator Training & Performance Management": {
        "icon": "👷",
        "capital_cost": 375.0,
        "productivity_delta": [0.0, 1.0, 2.0, 3.0],
        "quality_delta": [0.00, 0.01, 0.02, 0.03],
        "cost_reduction": [0.0, 1.0, 2.0, 3.0],
        "effect_lines": {
            "Productivity": "No change in Month 1, then increases by 1 tile/day in each subsequent active month.",
            "Quality": "No change in Month 1, then increases by 1 percentage point in each subsequent active month.",
            "Manufacturing Cost": "No change in Month 1, then decreases by 1 per tile in each subsequent active month.",
        },
    },
}

LEADERBOARD_PATH = "data/leaderboard.csv"
LOG_PATH = "data/simulation_log.csv"
LEADERBOARD_COLUMNS = [
    "Session ID", "Team Name", "Team Members", "Month", "Selected Activity",
    "Productivity", "Quality %", "Manufacturing Cost", "Landed Cost",
    "Selling Price", "Monthly Profit", "Cumulative Profit",
    "Capital Budget Remaining", "Updated At",
]
LOG_COLUMNS = [
    "Session ID", "Team Name", "Team Members", "Month", "Selected Activity",
    "Active Activity Stages", "Productivity", "Quality %", "Manufacturing Cost",
    "Capital Cost", "Landed Cost", "Selling Price", "Monthly Profit",
    "Cumulative Profit", "Capital Budget Remaining", "Diagnosis", "Created At",
]

# =============================================================================
# STYLE
# =============================================================================
st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 8% 4%,#dcfce7 0,transparent 22%),linear-gradient(135deg,#f8fffa,#eef7f0)}
.block-container{max-width:1360px;padding-top:1.1rem;padding-bottom:3rem}#MainMenu,footer{visibility:hidden}
.hero{padding:1.8rem 2rem;border-radius:25px;background:linear-gradient(125deg,#103d27,#166534 52%,#16a34a);color:white;box-shadow:0 18px 48px rgba(20,83,45,.2);margin-bottom:1rem}.hero h1{margin:0}.hero p{margin:.4rem 0 0;opacity:.92}
.baseline{padding:1rem 1.15rem;border-radius:16px;background:#ecfeff;border:1px solid #67e8f9;margin:.8rem 0}.insight{padding:.9rem 1rem;border-radius:14px;background:#eff6ff;border:1px solid #93c5fd;margin:.7rem 0}
.actionbar{display:flex;gap:8px;align-items:center;justify-content:center;margin:1rem 0 .8rem;padding:.8rem;border-radius:15px;background:white;border:1px solid #d9e8de}.step{min-width:125px;text-align:center;padding:.65rem .75rem;border-radius:12px;background:#e2e8f0;color:#475569;font-weight:750}.step.done{background:#bbf7d0;color:#14532d}.step.current{background:#15803d;color:white;box-shadow:0 6px 16px rgba(21,128,61,.25)}
.activity{background:white;border:1px solid #d9e8de;border-radius:18px;padding:1rem;box-shadow:0 8px 22px rgba(20,83,45,.07);height:100%}.activity.unavailable{opacity:.47;filter:grayscale(.7)}.activity h3{font-size:1.04rem;margin:.15rem 0 .45rem}.activity p{font-size:.86rem;color:#475569;line-height:1.5}.effect-summary{width:100%;border-collapse:collapse;margin-top:.55rem;font-size:.82rem}.effect-summary td{padding:.55rem .5rem;border-bottom:1px solid #dbe5df;vertical-align:top}.effect-summary td:first-child{width:31%;font-weight:800;color:#14532d;background:#f8fafc}.effect-summary tr:last-child td{border-bottom:0}.ico{font-size:2rem}.capital{margin-top:.7rem;padding:.5rem .65rem;border-radius:9px;background:#f0fdf4;color:#166534;font-weight:800}
.process-wrap{background:white;border:1px solid #b9d8c1;border-radius:22px;padding:1rem;overflow-x:auto}.process-line{min-width:1000px;display:flex;align-items:center;gap:10px;position:relative;padding:20px 10px 50px}.unit{width:145px;min-height:80px;border:2px solid #15803d;border-radius:13px;background:#eefbf1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-weight:750}.unit span{font-size:1.8rem}.arrow{width:48px;height:12px;background:#15803d;position:relative}.arrow:after{content:"";position:absolute;right:-13px;top:-7px;border-left:14px solid #15803d;border-top:13px solid transparent;border-bottom:13px solid transparent}.belt{position:absolute;left:15px;right:15px;bottom:18px;height:10px;border-radius:6px;background:repeating-linear-gradient(90deg,#14532d 0 24px,#86efac 24px 38px);animation:belt .75s linear infinite}.tile{position:absolute;bottom:29px;width:34px;height:20px;background:#f59e0b;border:2px solid #9a5a06;border-radius:3px;animation:move 8s linear infinite}.tile.t2{animation-delay:-2.7s}.tile.t3{animation-delay:-5.4s}.flow-label{position:absolute;bottom:0;left:15px;color:#166534;font-size:.78rem;font-weight:700}@keyframes belt{to{background-position:38px 0}}@keyframes move{0%{left:2%}100%{left:95%}}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;min-height:45px;font-weight:700}.stFormSubmitButton>button{background:#15803d!important;color:white!important;border:0!important}
</style>
""", unsafe_allow_html=True)

# =============================================================================
# OPTIONAL GITHUB STORAGE
# =============================================================================
def github_configured():
    return all(str(st.secrets.get(k, "")).strip() for k in ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"])

def github_headers():
    return {"Authorization":f"Bearer {st.secrets['GITHUB_TOKEN']}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}

def github_url(path):
    return f"https://api.github.com/repos/{st.secrets['GITHUB_OWNER']}/{st.secrets['GITHUB_REPO']}/contents/{path}"

def read_remote_csv(path, columns):
    response=requests.get(github_url(path),headers=github_headers(),params={"ref":st.secrets.get("GITHUB_BRANCH","main")},timeout=30)
    if response.status_code==404:return pd.DataFrame(columns=columns),None
    response.raise_for_status();payload=response.json()
    try:frame=pd.read_csv(io.BytesIO(base64.b64decode(payload["content"])))
    except pd.errors.EmptyDataError:frame=pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame:frame[column]=""
    return frame[columns],payload["sha"]

def write_remote_csv(path,frame,columns,sha,message):
    body={"message":message,"content":base64.b64encode(frame[columns].to_csv(index=False).encode()).decode(),"branch":st.secrets.get("GITHUB_BRANCH","main")}
    if sha:body["sha"]=sha
    response=requests.put(github_url(path),headers=github_headers(),json=body,timeout=30);response.raise_for_status()

def append_remote_csv(path,row,columns,message):
    frame,sha=read_remote_csv(path,columns);frame=pd.concat([frame,pd.DataFrame([row])],ignore_index=True);write_remote_csv(path,frame,columns,sha,message)

def update_leaderboard(row):
    if github_configured():
        frame,sha=read_remote_csv(LEADERBOARD_PATH,LEADERBOARD_COLUMNS);frame=frame[~frame["Session ID"].astype(str).eq(str(row["Session ID"]))];frame=pd.concat([frame,pd.DataFrame([row])],ignore_index=True);write_remote_csv(LEADERBOARD_PATH,frame,LEADERBOARD_COLUMNS,sha,"Update monthly profit leaderboard")
    local=st.session_state.get("local_lb",pd.DataFrame(columns=LEADERBOARD_COLUMNS));local=local[~local["Session ID"].astype(str).eq(str(row["Session ID"]))];st.session_state.local_lb=pd.concat([local,pd.DataFrame([row])],ignore_index=True)

def get_leaderboard():
    if github_configured():
        try:return read_remote_csv(LEADERBOARD_PATH,LEADERBOARD_COLUMNS)[0]
        except Exception as error:st.caption(f"Shared leaderboard unavailable: {error}")
    return st.session_state.get("local_lb",pd.DataFrame(columns=LEADERBOARD_COLUMNS))

# =============================================================================
# SIMULATION ENGINE
# =============================================================================
def initial_state():
    return {"month":0,"capital_budget":BASELINE["capital_budget"],"selections":{},"productivity":BASELINE["productivity"],"quality":BASELINE["quality"],"manufacturing_cost":BASELINE["manufacturing_cost"],"cumulative_profit":0.0,"history":[]}

def portfolio_metrics(selections,current_month,new_activity=None):
    # Earlier selections remain active and advance one maturity month even when
    # no new activity can be purchased because the capital budget is exhausted.
    active=dict(selections)
    if new_activity:
        active[current_month]=new_activity
    productivity=BASELINE["productivity"];quality=BASELINE["quality"];cost=BASELINE["manufacturing_cost"];stages=[]
    for selected_month,activity_name in sorted(active.items()):
        stage=current_month-selected_month
        activity=ACTIVITIES[activity_name]
        productivity+=activity["productivity_delta"][stage]
        quality+=activity["quality_delta"][stage]
        cost-=activity["cost_reduction"][stage]
        stages.append(f"{activity_name}: M{stage+1}")
    quality=max(0,min(1,quality));cost=max(0,cost)
    capital=ACTIVITIES[new_activity]["capital_cost"] if new_activity else 0.0
    good_tiles=productivity*quality
    landed=(productivity*cost+capital)/good_tiles if good_tiles else 0
    profit=good_tiles*BASELINE["selling_price"]-productivity*cost-capital
    return {"productivity":productivity,"quality":quality,"manufacturing_cost":cost,"capital_cost":capital,"landed_cost":landed,"monthly_profit":profit,"stages":" | ".join(stages) if stages else "Baseline only"}

def diagnosis(metrics,previous=None):
    parts=[
        f"Productivity is {'above' if metrics['productivity']>80 else 'at' if metrics['productivity']==80 else 'below'} the Month 0 baseline.",
        f"Quality is {'above' if metrics['quality']>.75 else 'at' if metrics['quality']==.75 else 'below'} the 75% baseline.",
        f"Manufacturing cost is {'below' if metrics['manufacturing_cost']<30 else 'at' if metrics['manufacturing_cost']==30 else 'above'} the baseline of 30/tile.",
    ]
    if previous:
        delta=metrics["monthly_profit"]-previous["monthly_profit"]
        parts.append(f"Monthly profit {'increased' if delta>=0 else 'decreased'} by {abs(delta):.1f} versus the previous month.")
    return " ".join(parts)

def run_month(continue_without_activity=False):
    state=st.session_state.state.copy();state["selections"]=dict(state["selections"]);state["history"]=list(state["history"])
    month=state["month"]+1
    selected=None if continue_without_activity else st.session_state.get("selected_activity")
    if not selected and not continue_without_activity:st.error("Select one activity for this month.");return
    if selected and selected in state["selections"].values():st.error("This activity has already been selected.");return
    capital=ACTIVITIES[selected]["capital_cost"] if selected else 0.0
    if capital>state["capital_budget"]:st.error("The selected activity exceeds the remaining capital budget.");return
    metrics=portfolio_metrics(state["selections"],month,selected);previous=state["history"][-1] if state["history"] else None
    selection_label=selected if selected else "No New Activity - Existing Effects Continue"
    metrics.update({"month":month,"selected":selection_label,"diagnosis":diagnosis(metrics,previous)})
    state["month"]=month;state["capital_budget"]-=capital
    if selected:state["selections"][month]=selected
    state["productivity"]=metrics["productivity"];state["quality"]=metrics["quality"];state["manufacturing_cost"]=metrics["manufacturing_cost"];state["cumulative_profit"]+=metrics["monthly_profit"];state["history"].append(metrics);st.session_state.state=state
    row={"Session ID":st.session_state.session_id,"Team Name":st.session_state.team_name,"Team Members":st.session_state.team_members,"Month":month,"Selected Activity":selection_label,"Productivity":metrics["productivity"],"Quality %":metrics["quality"]*100,"Manufacturing Cost":metrics["manufacturing_cost"],"Landed Cost":metrics["landed_cost"],"Selling Price":BASELINE["selling_price"],"Monthly Profit":metrics["monthly_profit"],"Cumulative Profit":state["cumulative_profit"],"Capital Budget Remaining":state["capital_budget"],"Updated At":datetime.now().strftime("%Y-%m-%d %H:%M:%S")};update_leaderboard(row)
    if github_configured():
        log={"Session ID":st.session_state.session_id,"Team Name":st.session_state.team_name,"Team Members":st.session_state.team_members,"Month":month,"Selected Activity":selection_label,"Active Activity Stages":metrics["stages"],"Productivity":metrics["productivity"],"Quality %":metrics["quality"]*100,"Manufacturing Cost":metrics["manufacturing_cost"],"Capital Cost":capital,"Landed Cost":metrics["landed_cost"],"Selling Price":BASELINE["selling_price"],"Monthly Profit":metrics["monthly_profit"],"Cumulative Profit":state["cumulative_profit"],"Capital Budget Remaining":state["capital_budget"],"Diagnosis":metrics["diagnosis"],"Created At":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        try:append_remote_csv(LOG_PATH,log,LOG_COLUMNS,f"Add Month {month} result")
        except Exception as error:st.warning(f"Month completed; GitHub save failed: {error}")
    st.rerun()

def continue_with_existing_effects():
    run_month(continue_without_activity=True)

# =============================================================================
# UI HELPERS
# =============================================================================
def hero():st.markdown("<div class='hero'><h1>🏆 Four-Month Profit Optimization Challenge</h1><p>Select one unique activity each month. Every selected activity remains active, matures month by month, and accumulates with all other active activities.</p></div>",unsafe_allow_html=True)

def conveyor(productivity):
    duration=max(2.8,min(14,900/max(productivity,1)))
    st.markdown(f"""<div class='process-wrap'><div class='process-line'><div class='unit'><span>🧱</span>Inputs</div><div class='arrow'></div><div class='unit'><span>🏭</span>Production</div><div class='arrow'></div><div class='unit'><span>✅</span>Quality</div><div class='arrow'></div><div class='unit'><span>🚚</span>Landed Cost</div><div class='arrow'></div><div class='unit'><span>💰</span>Profit</div><div class='belt'></div><div class='tile' style='animation-duration:{duration}s'></div><div class='tile t2' style='animation-duration:{duration}s'></div><div class='tile t3' style='animation-duration:{duration}s'></div><div class='flow-label'>Conveyor speed linked to productivity: {productivity:.1f} tiles/day</div></div></div>""",unsafe_allow_html=True)

def month_bar(current):
    boxes=[]
    for month in range(1,5):
        css="done" if month<=current else "current" if month==current+1 else ""
        label="Completed" if month<=current else "Select Now" if month==current+1 else "Upcoming"
        boxes.append(f"<div class='step {css}'>Month {month}<br><small>{label}</small></div>")
    st.markdown("<div class='actionbar'>"+"".join(boxes)+"</div>",unsafe_allow_html=True)

def activity_card(name,activity,unavailable):
    css="activity unavailable" if unavailable else "activity"
    lines=activity["effect_lines"]
    return f"""<div class='{css}'><div class='ico'>{activity['icon']}</div><h3>{name}</h3><table class='effect-summary'><tr><td>Productivity</td><td>{lines['Productivity']}</td></tr><tr><td>Quality</td><td>{lines['Quality']}</td></tr><tr><td>Manufacturing Cost</td><td>{lines['Manufacturing Cost']}</td></tr></table><div class='capital'>Capital Cost: {activity['capital_cost']:,.0f}</div></div>"""

def result_trend(history):
    frame=pd.DataFrame(history);x=[f"Month {int(m)}" for m in frame["month"]];fig=go.Figure();fig.add_bar(x=x,y=frame["monthly_profit"],name="Monthly Profit",marker_color="#15803d");fig.add_scatter(x=x,y=frame["landed_cost"],name="Landed Cost",yaxis="y2",mode="lines+markers",line=dict(color="#f59e0b"));fig.update_layout(title="Monthly Profit and Landed Cost",yaxis_title="Monthly Profit",yaxis2=dict(title="Landed Cost",overlaying="y",side="right"));st.plotly_chart(fig,use_container_width=True)

def leaderboard_section():
    st.subheader("🏅 Live Leaderboard");lb=get_leaderboard()
    if lb.empty:st.info("Complete a month to populate the leaderboard.");return
    for column in ["Cumulative Profit","Capital Budget Remaining"]:lb[column]=pd.to_numeric(lb[column],errors="coerce")
    lb=lb.sort_values(["Cumulative Profit","Capital Budget Remaining"],ascending=[False,False]).reset_index(drop=True);lb.insert(0,"Rank",range(1,len(lb)+1));st.dataframe(lb[["Rank","Team Name","Team Members","Month","Selected Activity","Cumulative Profit","Capital Budget Remaining"]],use_container_width=True,hide_index=True)

# =============================================================================
# PAGES
# =============================================================================
def registration_page():
    hero();conveyor(BASELINE["productivity"]);_,center,_=st.columns([1,1.5,1])
    with center:
        with st.form("registration"):
            st.subheader("Register Your Team");team=st.text_input("Team Name *");members=st.text_area("Team Members *",height=110);submitted=st.form_submit_button("Start Challenge →",use_container_width=True)
        if submitted:
            if not team.strip() or not members.strip():st.error("Enter both Team Name and Team Members.")
            else:st.session_state.update(registered=True,session_id=str(uuid.uuid4()),team_name=team.strip(),team_members=members.strip(),state=initial_state(),local_lb=pd.DataFrame(columns=LEADERBOARD_COLUMNS));st.rerun()

def dashboard_page():
    hero();state=st.session_state.state;conveyor(state["productivity"])
    with st.sidebar:
        st.success(f"Team: {st.session_state.team_name}");st.write("**Team Members**");st.write(st.session_state.team_members);st.metric("Month",f"{state['month']} / 4");st.metric("Capital Budget",f"{state['capital_budget']:,.0f}");st.metric("Cumulative Profit",f"{state['cumulative_profit']:,.1f}")
        if st.button("Restart Simulation",use_container_width=True):st.session_state.clear();st.rerun()
    if not state["history"]:
        baseline_profit=80*.75*50-80*30
        st.markdown(f"<div class='baseline'><h3>Month 0 Baseline</h3><p><b>Productivity:</b> 80 tiles/day &nbsp; | &nbsp; <b>Quality:</b> 75% &nbsp; | &nbsp; <b>Manufacturing Cost:</b> 30/tile &nbsp; | &nbsp; <b>Selling Price:</b> 50/tile &nbsp; | &nbsp; <b>Capital Budget:</b> 1,500</p><p>Baseline monthly profit before any activity: {baseline_profit:,.1f}</p></div>",unsafe_allow_html=True)
    else:
        latest=state["history"][-1];m1,m2,m3,m4,m5=st.columns(5);m1.metric("Productivity",f"{latest['productivity']:.1f}");m2.metric("Quality",f"{latest['quality']:.1%}");m3.metric("Manufacturing Cost",f"{latest['manufacturing_cost']:.1f}");m4.metric("Landed Cost",f"{latest['landed_cost']:.2f}");m5.metric("Monthly Profit",f"{latest['monthly_profit']:,.1f}");st.markdown(f"<div class='insight'><b>Month {state['month']} diagnosis:</b> {latest['diagnosis']}<br><b>Accumulated active effects:</b> {latest['stages']}</div>",unsafe_allow_html=True);result_trend(state["history"])

    month_bar(state["month"])

    if state["month"]<4:
        month=state["month"]+1;used=set(state["selections"].values());available=[name for name,a in ACTIVITIES.items() if name not in used and a["capital_cost"]<=state["capital_budget"]]
        st.subheader(f"Month {month}: Select One Activity")
        st.caption("An activity can be selected only once. Earlier activities remain active and their incremental effects continue to combine with every later activity.")
        cols=st.columns(2)
        for index,(name,activity) in enumerate(ACTIVITIES.items()):
            with cols[index%2]:st.markdown(activity_card(name,activity,name in used or activity["capital_cost"]>state["capital_budget"]),unsafe_allow_html=True)
        if available:
            selected=st.selectbox("Choose the Month activity",available,index=None,placeholder="Select one activity",key=f"selection_month_{month}");st.session_state.selected_activity=selected
            if selected:
                capital=ACTIVITIES[selected]["capital_cost"];a,b,c=st.columns(3);a.metric("Current Capital Budget",f"{state['capital_budget']:,.0f}");b.metric("Selected Capital Cost",f"{capital:,.0f}");c.metric("Budget After",f"{state['capital_budget']-capital:,.0f}")
            st.button(f"Run Month {month} ▶",type="primary",use_container_width=True,disabled=not selected,on_click=run_month)
        else:
            st.session_state.selected_activity=None
            st.info("No unused activity is affordable with the remaining capital budget. Continue to the next month so all previously selected activities mature and their remaining effects are applied.")
            st.button(f"Continue to Month {month} with Existing Effects ▶",type="primary",use_container_width=True,on_click=continue_with_existing_effects)
    else:
        st.success(f"Simulation complete. Four-month cumulative profit: {state['cumulative_profit']:,.1f}. Capital budget remaining: {state['capital_budget']:,.1f}.")
        st.info("Leaderboard ranking is based only on cumulative profit. Unspent capital budget carries no penalty.")
    leaderboard_section()

if st.session_state.get("registered"):dashboard_page()
else:registration_page()
