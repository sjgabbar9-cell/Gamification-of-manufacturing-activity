import base64
import json
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
# BASELINE AND ACTIVITY MODEL
# Incremental values are applied once in the relevant ACTIVE month.
# Example: [10, 0, 0, 0] means +10 products/month when the activity is activated,
# then no further increase; the improved KPI is carried forward automatically.
# =============================================================================
BASELINE = {
    "productivity": 80.0,                 # products/month
    "quality": 0.75,                      # proportion
    "manufacturing_cost": 30.0,           # cost/product
    "selling_price": 50.0,                # price/product
    "capital_budget": 1500.0,
}

ACTIVITIES = {
    "Parallel Line Installation": {
        "icon": "🏭",
        "capital_cost": 750.0,
        "productivity_increment": [5.0, 0.0, 0.0, 0.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [1.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "Increases by 5 products/month in the activation month; no further increment is added, so the improved level remains constant.",
            "Quality": "No change in the activation month or later active months.",
            "Manufacturing Cost": "Decreases by 1 per product in the activation month; no further reduction is added, so the reduced level remains constant.",
        },
    },
    "Changeover Time Optimization (SMED)": {
        "icon": "⏱️",
        "capital_cost": 375.0,
        "productivity_increment": [5.0, 1.0, 1.0, 1.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [2.0, 1.0, 1.0, 1.0],
        "effect_lines": {
            "Productivity": "Increases by 5 products/month in the activation month, then by 1 product/month in each subsequent active month.",
            "Quality": "No change in the activation month or later active months.",
            "Manufacturing Cost": "Decreases by 2 per product in the activation month, then by 1 per product in each subsequent active month.",
        },
    },
    "Increase Speed of Bottleneck": {
        "icon": "⚙️",
        "capital_cost": 150.0,
        "productivity_increment": [1.0, 0.0, 0.0, 0.0],
        "quality_increment": [-0.05, -0.05, -0.05, -0.05],
        "cost_reduction_increment": [0.0, 0.0, 0.0, 0.0],
        "effect_lines": {
            "Productivity": "Increases by 1 product/month in the activation month; no further productivity increment is added.",
            "Quality": "Decreases by 5 percentage points in every active month, representing the continuing quality risk of sustained high-speed operation.",
            "Manufacturing Cost": "No manufacturing-cost reduction is achieved in any active month.",
        },
    },
    "Preventive Maintenance (CLTI)": {
        "icon": "🔧",
        "capital_cost": 300.0,
        "productivity_increment": [1.0, 1.0, 1.0, 1.0],
        "quality_increment": [0.00, 0.00, 0.00, 0.00],
        "cost_reduction_increment": [0.0, 1.0, 1.0, 1.0],
        "effect_lines": {
            "Productivity": "Increases by 1 product/month in each active month, giving a total increase of 4 products/month by Active Month 4.",
            "Quality": "No change in any active month.",
            "Manufacturing Cost": "No change in Active Month 1, then decreases by 1 per product in each subsequent active month.",
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
            "Quality": "Increases by 3 percentage points in each active month, giving a total increase of 12 percentage points by Active Month 4.",
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
            "Productivity": "No change in Active Month 1, then increases by 1 product/month in each subsequent active month.",
            "Quality": "No change in Active Month 1, then increases by 1 percentage point in each subsequent active month.",
            "Manufacturing Cost": "No change in Active Month 1, then decreases by 1 per product in each subsequent active month.",
        },
    },
}

# =============================================================================
# SHARED LEADERBOARD CONFIGURATION
# One JSON file per browser session prevents one player from overwriting another.
# =============================================================================
LEADERBOARD_FOLDER = "data/leaderboard_sessions"


def github_configured():
    return all(
        str(st.secrets.get(key, "")).strip()
        for key in ["GITHUB_TOKEN", "GITHUB_OWNER", "GITHUB_REPO"]
    )


def github_headers():
    return {
        "Authorization": f"Bearer {st.secrets['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_url(path):
    return (
        f"https://api.github.com/repos/{st.secrets['GITHUB_OWNER']}/"
        f"{st.secrets['GITHUB_REPO']}/contents/{path}"
    )


def branch_name():
    return st.secrets.get("GITHUB_BRANCH", "main")


def get_file(path):
    response = requests.get(
        github_url(path),
        headers=github_headers(),
        params={"ref": branch_name()},
        timeout=30,
    )
    if response.status_code == 404:
        return None, None
    response.raise_for_status()
    payload = response.json()
    return base64.b64decode(payload["content"]).decode("utf-8"), payload["sha"]


def put_json(path, record, message):
    for attempt in range(4):
        _, sha = get_file(path)
        body = {
            "message": message,
            "content": base64.b64encode(
                json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("ascii"),
            "branch": branch_name(),
        }
        if sha:
            body["sha"] = sha
        response = requests.put(
            github_url(path), headers=github_headers(), json=body, timeout=30
        )
        if response.status_code in (200, 201):
            return
        if response.status_code not in (409, 422) or attempt == 3:
            response.raise_for_status()


def session_path(session_id):
    safe_id = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")
    return f"{LEADERBOARD_FOLDER}/{safe_id}.json"


def save_player(record):
    local = st.session_state.get("local_players", {})
    local[str(record["Session ID"])] = record
    st.session_state.local_players = local
    if github_configured():
        put_json(
            session_path(record["Session ID"]),
            record,
            f"Update leaderboard player {record['Team Name']}",
        )


def shared_players():
    records = {}
    if github_configured():
        response = requests.get(
            github_url(LEADERBOARD_FOLDER),
            headers=github_headers(),
            params={"ref": branch_name()},
            timeout=30,
        )
        if response.status_code not in (200, 404):
            response.raise_for_status()
        if response.status_code == 200:
            for item in response.json():
                if item.get("type") != "file" or not item.get("name", "").endswith(".json"):
                    continue
                try:
                    file_response = requests.get(
                        item["url"], headers=github_headers(), timeout=30
                    )
                    file_response.raise_for_status()
                    payload = file_response.json()
                    record = json.loads(
                        base64.b64decode(payload["content"]).decode("utf-8")
                    )
                    records[str(record["Session ID"])] = record
                except Exception:
                    continue

    for session_id, local_record in st.session_state.get("local_players", {}).items():
        shared_record = records.get(session_id)
        if not shared_record or str(local_record.get("Updated At", "")) >= str(
            shared_record.get("Updated At", "")
        ):
            records[session_id] = local_record
    return list(records.values())

# =============================================================================
# SIMULATION ENGINE
# =============================================================================
def initial_state():
    return {
        "month": 0,
        "capital_budget": BASELINE["capital_budget"],
        "selections": {},
        "productivity": BASELINE["productivity"],
        "quality": BASELINE["quality"],
        "manufacturing_cost": BASELINE["manufacturing_cost"],
        "cumulative_profit": 0.0,
        "history": [],
    }


def calculate_month(state, current_month, new_activity=None):
    """
    Stateful incremental calculation.

    The calculation starts from the previous month's KPI values, not Month 0.
    Every active activity contributes only the increment corresponding to its
    current ACTIVE month. Example for SMED selected in calendar Month 2:
      calendar Month 2 -> active M1 -> +10 products/month
      calendar Month 3 -> active M2 -> +0
      calendar Month 4 -> active M3 -> +0
    The +10 remains because Month 3 starts from Month 2's ending productivity.
    """
    productivity = state["productivity"]
    quality = state["quality"]
    manufacturing_cost = state["manufacturing_cost"]

    active_selections = dict(state["selections"])
    if new_activity:
        active_selections[current_month] = new_activity

    applied_effects = []
    active_stages = []
    for activation_month, activity_name in sorted(active_selections.items()):
        active_month_index = current_month - activation_month
        activity = ACTIVITIES[activity_name]

        productivity_change = activity["productivity_increment"][active_month_index]
        quality_change = activity["quality_increment"][active_month_index]
        cost_reduction = activity["cost_reduction_increment"][active_month_index]

        productivity += productivity_change
        quality += quality_change
        manufacturing_cost -= cost_reduction

        active_stages.append(f"{activity_name}: Active M{active_month_index + 1}")
        applied_effects.append(
            f"{activity_name} | productivity {productivity_change:+.1f} products/month, "
            f"quality {quality_change * 100:+.1f} pp, "
            f"cost {(-cost_reduction):+.1f}/product"
        )

    quality = max(0.0, min(1.0, quality))
    manufacturing_cost = max(0.0, manufacturing_cost)
    capital_cost = ACTIVITIES[new_activity]["capital_cost"] if new_activity else 0.0
    good_products = productivity * quality
    landed_cost = (
        (productivity * manufacturing_cost + capital_cost) / good_products
        if good_products
        else 0.0
    )
    monthly_profit = (
        good_products * BASELINE["selling_price"]
        - productivity * manufacturing_cost
        - capital_cost
    )

    return {
        "productivity": productivity,
        "quality": quality,
        "manufacturing_cost": manufacturing_cost,
        "capital_cost": capital_cost,
        "landed_cost": landed_cost,
        "monthly_profit": monthly_profit,
        "active_stages": " | ".join(active_stages) if active_stages else "Baseline only",
        "applied_effects": " | ".join(applied_effects) if applied_effects else "No change",
    }


def diagnosis(metrics, previous=None):
    parts = [
        f"Productivity is {'above' if metrics['productivity'] > 80 else 'at' if metrics['productivity'] == 80 else 'below'} the Month 0 baseline.",
        f"Quality is {'above' if metrics['quality'] > .75 else 'at' if metrics['quality'] == .75 else 'below'} the 75% baseline.",
        f"Manufacturing cost is {'below' if metrics['manufacturing_cost'] < 30 else 'at' if metrics['manufacturing_cost'] == 30 else 'above'} the baseline of 30 per product.",
    ]
    if previous:
        difference = metrics["monthly_profit"] - previous["monthly_profit"]
        parts.append(
            f"Monthly profit {'increased' if difference >= 0 else 'decreased'} "
            f"by {abs(difference):.1f} versus the previous month."
        )
    return " ".join(parts)


def player_record(state, selected_activity="Registered - Not Started"):
    latest = state["history"][-1] if state["history"] else None
    return {
        "Session ID": st.session_state.session_id,
        "Team Name": st.session_state.team_name,
        "Team Members": st.session_state.team_members,
        "Month": state["month"],
        "Selected Activity": selected_activity,
        "Productivity": latest["productivity"] if latest else BASELINE["productivity"],
        "Quality %": (latest["quality"] if latest else BASELINE["quality"]) * 100,
        "Manufacturing Cost": latest["manufacturing_cost"] if latest else BASELINE["manufacturing_cost"],
        "Landed Cost": latest["landed_cost"] if latest else BASELINE["manufacturing_cost"] / BASELINE["quality"],
        "Monthly Profit": latest["monthly_profit"] if latest else 0.0,
        "Cumulative Profit": state["cumulative_profit"],
        "Capital Budget Remaining": state["capital_budget"],
        "Updated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
    }


def run_month(continue_without_activity=False):
    state = st.session_state.state.copy()
    state["selections"] = dict(state["selections"])
    state["history"] = list(state["history"])
    month = state["month"] + 1
    selected = None if continue_without_activity else st.session_state.get("selected_activity")

    if not selected and not continue_without_activity:
        st.error("Select one activity for this month.")
        return
    if selected and selected in state["selections"].values():
        st.error("This activity has already been selected.")
        return

    capital_cost = ACTIVITIES[selected]["capital_cost"] if selected else 0.0
    if capital_cost > state["capital_budget"]:
        st.error("The selected activity exceeds the remaining capital budget.")
        return

    metrics = calculate_month(state, month, selected)
    previous = state["history"][-1] if state["history"] else None
    selection_label = selected if selected else "No New Activity - Existing Effects Continue"
    metrics.update(
        {
            "month": month,
            "selected": selection_label,
            "diagnosis": diagnosis(metrics, previous),
        }
    )

    state["month"] = month
    state["capital_budget"] -= capital_cost
    if selected:
        state["selections"][month] = selected
    state["productivity"] = metrics["productivity"]
    state["quality"] = metrics["quality"]
    state["manufacturing_cost"] = metrics["manufacturing_cost"]
    state["cumulative_profit"] += metrics["monthly_profit"]
    state["history"].append(metrics)
    st.session_state.state = state

    try:
        save_player(player_record(state, selection_label))
    except Exception as error:
        st.warning(f"Month completed, but the shared leaderboard update failed: {error}")
    st.rerun()


def continue_with_existing_effects():
    run_month(continue_without_activity=True)

# =============================================================================
# UI STYLE
# =============================================================================
st.markdown(
    """
<style>
.stApp{background:radial-gradient(circle at 8% 4%,#dcfce7 0,transparent 22%),linear-gradient(135deg,#f8fffa,#eef7f0)}
.block-container{max-width:1360px;padding-top:1.1rem;padding-bottom:3rem}#MainMenu,footer{visibility:hidden}
.hero{padding:1.8rem 2rem;border-radius:25px;background:linear-gradient(125deg,#103d27,#166534 52%,#16a34a);color:white;box-shadow:0 18px 48px rgba(20,83,45,.2);margin-bottom:1rem}.hero h1{margin:0}.hero p{margin:.4rem 0 0;opacity:.92}
.baseline{padding:1rem 1.15rem;border-radius:16px;background:#ecfeff;border:1px solid #67e8f9;margin:.8rem 0}.insight{padding:.9rem 1rem;border-radius:14px;background:#eff6ff;border:1px solid #93c5fd;margin:.7rem 0}
.actionbar{display:flex;gap:8px;align-items:center;justify-content:center;margin:1rem 0 .8rem;padding:.8rem;border-radius:15px;background:white;border:1px solid #d9e8de}.step{min-width:125px;text-align:center;padding:.65rem .75rem;border-radius:12px;background:#e2e8f0;color:#475569;font-weight:750}.step.done{background:#bbf7d0;color:#14532d}.step.current{background:#15803d;color:white;box-shadow:0 6px 16px rgba(21,128,61,.25)}
.activity{background:white;border:1px solid #d9e8de;border-radius:18px;padding:1rem;box-shadow:0 8px 22px rgba(20,83,45,.07);height:100%}.activity.unavailable{opacity:.47;filter:grayscale(.7)}.activity h3{font-size:1.04rem;margin:.15rem 0 .45rem}.ico{font-size:2rem}.capital{margin-top:.7rem;padding:.5rem .65rem;border-radius:9px;background:#f0fdf4;color:#166534;font-weight:800}
.effect-summary{width:100%;border-collapse:collapse;margin-top:.55rem;font-size:.82rem}.effect-summary td{padding:.55rem .5rem;border-bottom:1px solid #dbe5df;vertical-align:top}.effect-summary td:first-child{width:31%;font-weight:800;color:#14532d;background:#f8fafc}.effect-summary tr:last-child td{border-bottom:0}
.process-wrap{background:white;border:1px solid #b9d8c1;border-radius:22px;padding:1rem;overflow-x:auto}.process-line{min-width:1000px;display:flex;align-items:center;gap:10px;position:relative;padding:20px 10px 50px}.unit{width:145px;min-height:80px;border:2px solid #15803d;border-radius:13px;background:#eefbf1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-weight:750}.unit span{font-size:1.8rem}.arrow{width:48px;height:12px;background:#15803d;position:relative}.arrow:after{content:"";position:absolute;right:-13px;top:-7px;border-left:14px solid #15803d;border-top:13px solid transparent;border-bottom:13px solid transparent}.belt{position:absolute;left:15px;right:15px;bottom:18px;height:10px;border-radius:6px;background:repeating-linear-gradient(90deg,#14532d 0 24px,#86efac 24px 38px);animation:belt .75s linear infinite}.tile{position:absolute;bottom:29px;width:34px;height:20px;background:#f59e0b;border:2px solid #9a5a06;border-radius:3px;animation:move 8s linear infinite}.tile.t2{animation-delay:-2.7s}.tile.t3{animation-delay:-5.4s}.flow-label{position:absolute;bottom:0;left:15px;color:#166534;font-size:.78rem;font-weight:700}@keyframes belt{to{background-position:38px 0}}@keyframes move{0%{left:2%}100%{left:95%}}
.stButton>button,.stFormSubmitButton>button{border-radius:12px;min-height:45px;font-weight:700}.stFormSubmitButton>button{background:#15803d!important;color:white!important;border:0!important}
</style>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# UI HELPERS
# =============================================================================
def hero():
    st.markdown(
        "<div class='hero'><h1>🏆 Four-Month Profit Optimization Challenge</h1>"
        "<p>Select one unique activity each month. Effects are incremental by the "
        "activity's active month and remain accumulated in all later calendar months.</p></div>",
        unsafe_allow_html=True,
    )


def conveyor(productivity):
    duration = max(2.8, min(14, 900 / max(productivity, 1)))
    st.markdown(
        f"""<div class='process-wrap'><div class='process-line'>
        <div class='unit'><span>🧱</span>Inputs</div><div class='arrow'></div>
        <div class='unit'><span>🏭</span>Production</div><div class='arrow'></div>
        <div class='unit'><span>✅</span>Quality</div><div class='arrow'></div>
        <div class='unit'><span>🚚</span>Landed Cost</div><div class='arrow'></div>
        <div class='unit'><span>💰</span>Profit</div><div class='belt'></div>
        <div class='tile' style='animation-duration:{duration}s'></div>
        <div class='tile t2' style='animation-duration:{duration}s'></div>
        <div class='tile t3' style='animation-duration:{duration}s'></div>
        <div class='flow-label'>Conveyor speed linked to productivity: {productivity:.1f} products/month</div>
        </div></div>""",
        unsafe_allow_html=True,
    )


def month_bar(current):
    boxes = []
    for month in range(1, 5):
        css = "done" if month <= current else "current" if month == current + 1 else ""
        label = "Completed" if month <= current else "Select Now" if month == current + 1 else "Upcoming"
        boxes.append(f"<div class='step {css}'>Month {month}<br><small>{label}</small></div>")
    st.markdown("<div class='actionbar'>" + "".join(boxes) + "</div>", unsafe_allow_html=True)


def activity_card(name, activity, unavailable):
    css = "activity unavailable" if unavailable else "activity"
    lines = activity["effect_lines"]
    return f"""<div class='{css}'><div class='ico'>{activity['icon']}</div><h3>{name}</h3>
    <table class='effect-summary'>
    <tr><td>Productivity<br><small>(products/month)</small></td><td>{lines['Productivity']}</td></tr>
    <tr><td>Quality<br><small>(percentage points)</small></td><td>{lines['Quality']}</td></tr>
    <tr><td>Manufacturing Cost<br><small>(cost/product)</small></td><td>{lines['Manufacturing Cost']}</td></tr>
    </table><div class='capital'>Capital Cost: {activity['capital_cost']:,.0f}</div></div>"""


def result_trend(history):
    frame = pd.DataFrame(history)
    labels = [f"Month {int(value)}" for value in frame["month"]]
    figure = go.Figure()
    figure.add_bar(
        x=labels,
        y=frame["monthly_profit"],
        name="Monthly Profit",
        marker_color="#15803d",
    )
    figure.add_scatter(
        x=labels,
        y=frame["landed_cost"],
        name="Landed Cost",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color="#f59e0b"),
    )
    figure.update_layout(
        title="Monthly Profit and Landed Cost",
        yaxis_title="Monthly Profit",
        yaxis2=dict(title="Landed Cost / Good Product", overlaying="y", side="right"),
    )
    st.plotly_chart(figure, use_container_width=True)


def leaderboard_section():
    st.subheader("🏅 Live Shared Leaderboard")
    try:
        records = shared_players()
    except Exception as error:
        records = list(st.session_state.get("local_players", {}).values())
        st.warning(f"Shared leaderboard could not be refreshed: {error}")

    if not records:
        st.info("Registered players will appear here immediately.")
        return

    frame = pd.DataFrame(records)
    for column in ["Month", "Cumulative Profit", "Capital Budget Remaining"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    frame = frame.sort_values(
        ["Cumulative Profit", "Month", "Updated At"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    frame.insert(0, "Rank", range(1, len(frame) + 1))
    st.dataframe(
        frame[
            [
                "Rank",
                "Team Name",
                "Team Members",
                "Month",
                "Selected Activity",
                "Cumulative Profit",
                "Capital Budget Remaining",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    if not github_configured():
        st.caption("Cross-device shared results require GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO, and GITHUB_BRANCH in Streamlit secrets.")

# =============================================================================
# PAGES
# =============================================================================
def registration_page():
    hero()
    conveyor(BASELINE["productivity"])
    _, center, _ = st.columns([1, 1.5, 1])
    with center:
        with st.form("registration"):
            st.subheader("Register Your Team")
            team = st.text_input("Team Name *")
            members = st.text_area("Team Members *", height=110)
            submitted = st.form_submit_button("Start Challenge →", use_container_width=True)
        if submitted:
            if not team.strip() or not members.strip():
                st.error("Enter both Team Name and Team Members.")
            else:
                st.session_state.update(
                    registered=True,
                    session_id=str(uuid.uuid4()),
                    team_name=team.strip(),
                    team_members=members.strip(),
                    state=initial_state(),
                    local_players={},
                )
                try:
                    save_player(player_record(st.session_state.state))
                except Exception as error:
                    st.warning(f"Registration succeeded, but leaderboard registration failed: {error}")
                st.rerun()


def dashboard_page():
    hero()
    state = st.session_state.state
    conveyor(state["productivity"])

    with st.sidebar:
        st.success(f"Team: {st.session_state.team_name}")
        st.write("**Team Members**")
        st.write(st.session_state.team_members)
        st.metric("Month", f"{state['month']} / 4")
        st.metric("Capital Budget", f"{state['capital_budget']:,.0f}")
        st.metric("Cumulative Profit", f"{state['cumulative_profit']:,.1f}")
        if st.button("Restart Simulation", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if not state["history"]:
        baseline_profit = 80 * .75 * 50 - 80 * 30
        st.markdown(
            f"<div class='baseline'><h3>Month 0 Baseline</h3><p>"
            f"<b>Productivity:</b> 80 products/month &nbsp; | &nbsp; "
            f"<b>Quality:</b> 75% &nbsp; | &nbsp; "
            f"<b>Manufacturing Cost:</b> 30/product &nbsp; | &nbsp; "
            f"<b>Selling Price:</b> 50/product &nbsp; | &nbsp; "
            f"<b>Capital Budget:</b> 1,500</p>"
            f"<p>Baseline monthly profit before any activity: {baseline_profit:,.1f}</p></div>",
            unsafe_allow_html=True,
        )
    else:
        latest = state["history"][-1]
        metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
        metric_1.metric("Productivity", f"{latest['productivity']:.1f} products/month")
        metric_2.metric("Quality", f"{latest['quality']:.1%}")
        metric_3.metric("Manufacturing Cost", f"{latest['manufacturing_cost']:.1f}/product")
        metric_4.metric("Landed Cost", f"{latest['landed_cost']:.2f}/good product")
        metric_5.metric("Monthly Profit", f"{latest['monthly_profit']:,.1f}")
        st.markdown(
            f"<div class='insight'><b>Month {state['month']} diagnosis:</b> "
            f"{latest['diagnosis']}<br><b>Active activity age:</b> "
            f"{latest['active_stages']}<br><b>Increment applied this month:</b> "
            f"{latest['applied_effects']}</div>",
            unsafe_allow_html=True,
        )
        result_trend(state["history"])

    month_bar(state["month"])

    if state["month"] < 4:
        month = state["month"] + 1
        used = set(state["selections"].values())
        available = [
            name
            for name, activity in ACTIVITIES.items()
            if name not in used
            and activity["capital_cost"] <= state["capital_budget"]
        ]
        st.subheader(f"Month {month}: Select One Activity")
        st.caption(
            "Each row shows the increment by the activity's active month. "
            "Previously achieved KPI improvements remain in the process state."
        )

        columns = st.columns(2)
        for index, (name, activity) in enumerate(ACTIVITIES.items()):
            unavailable = (
                name in used
                or activity["capital_cost"] > state["capital_budget"]
            )
            with columns[index % 2]:
                st.markdown(
                    activity_card(name, activity, unavailable),
                    unsafe_allow_html=True,
                )

        if available:
            selected = st.selectbox(
                "Choose the Month activity",
                available,
                index=None,
                placeholder="Select one activity",
                key=f"selection_month_{month}",
            )
            st.session_state.selected_activity = selected
            if selected:
                capital_cost = ACTIVITIES[selected]["capital_cost"]
                current, selected_cost, after = st.columns(3)
                current.metric("Current Capital Budget", f"{state['capital_budget']:,.0f}")
                selected_cost.metric("Selected Capital Cost", f"{capital_cost:,.0f}")
                after.metric("Budget After", f"{state['capital_budget'] - capital_cost:,.0f}")
            st.button(
                f"Run Month {month} ▶",
                type="primary",
                use_container_width=True,
                disabled=not selected,
                on_click=run_month,
            )
        else:
            st.session_state.selected_activity = None
            st.info(
                "No unused activity is affordable. Continue so all existing "
                "activities advance to their next active month and apply only "
                "that active month's incremental effect."
            )
            st.button(
                f"Continue to Month {month} with Existing Effects ▶",
                type="primary",
                use_container_width=True,
                on_click=continue_with_existing_effects,
            )
    else:
        st.success(
            f"Simulation complete. Four-month cumulative profit: "
            f"{state['cumulative_profit']:,.1f}. Capital budget remaining: "
            f"{state['capital_budget']:,.1f}."
        )
        st.info(
            "Leaderboard ranking is based only on cumulative profit. "
            "Unspent capital budget carries no penalty."
        )

    leaderboard_section()


if st.session_state.get("registered"):
    dashboard_page()
else:
    registration_page()
