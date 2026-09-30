import base64, json, uuid
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Four-Month Profit Optimization Challenge",page_icon="🏆",layout="wide",initial_sidebar_state="expanded")

BASELINE={"productivity":80.0,"quality":.75,"manufacturing_cost":30.0,"selling_price":50.0,"capital_budget":1500.0}
ACTIVITIES={
"Parallel Line Installation":{"icon":"🏭","capital_cost":750.0,"p":[5,0,0,0],"q":[0,0,0,0],"c":[1,0,0,0],"lines":["+5 products/month in activation month; improved level remains.","No change.","-1 cost/product in activation month; reduced level remains."]},
"Changeover Time Optimization (SMED)":{"icon":"⏱️","capital_cost":375.0,"p":[5,1,1,1],"q":[0,0,0,0],"c":[2,1,1,1],"lines":["+5 products/month in activation month, then +1 in each later active month.","No change.","-2 cost/product in activation month, then -1 in each later active month."]},
"Increase Speed of Bottleneck":{"icon":"⚙️","capital_cost":150.0,"p":[1,0,0,0],"q":[-.05,-.05,-.05,-.05],"c":[0,0,0,0],"lines":["+1 product/month in activation month; no later increment.","-5 percentage points in every active month.","No change."]},
"Preventive Maintenance (CLTI)":{"icon":"🔧","capital_cost":300.0,"p":[1,1,1,1],"q":[0,0,0,0],"c":[0,1,1,1],"lines":["+1 product/month in every active month.","No change.","No change in Active M1, then -1 cost/product in each later active month."]},
"Statistical Process Control":{"icon":"📊","capital_cost":300.0,"p":[0,0,0,0],"q":[.03,.03,.03,.03],"c":[0,0,0,0],"lines":["No change.","+3 percentage points in every active month.","No change."]},
"Operator Training & Performance Management":{"icon":"👷","capital_cost":375.0,"p":[0,1,1,1],"q":[0,.01,.01,.01],"c":[0,1,1,1],"lines":["No change in Active M1, then +1 product/month in each later active month.","No change in Active M1, then +1 percentage point in each later active month.","No change in Active M1, then -1 cost/product in each later active month."]}}
LEADERBOARD_FILE="data/leaderboard.json"

st.markdown("""<style>
.stApp{background:#f5fbf7}.block-container{max-width:1380px;padding-top:1rem}.hero{padding:1.5rem 1.8rem;border-radius:22px;background:linear-gradient(120deg,#123d29,#15803d);color:white;margin-bottom:1rem}.hero h1{margin:0}.hero p{margin:.4rem 0 0}.kpi-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:1rem 0}.kpi{min-width:0;background:#f1faf4;border:1px solid #cde2d2;border-radius:18px;padding:1rem}.kl{font-size:.9rem;color:#234535}.kv{font-size:clamp(1.25rem,2.1vw,2.05rem);line-height:1.05;margin-top:.5rem;overflow-wrap:anywhere}.ku{display:block;font-size:.72rem;color:#526b5e;margin-top:.35rem}.summary{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden;margin:1rem 0}.summary th{background:#166534;color:white;padding:.65rem;text-align:center}.summary td{border:1px solid #d8e5dc;padding:.58rem;text-align:center}.summary td:first-child{font-weight:750;text-align:left}.summary tr:last-child td{background:#ecfdf5;font-weight:800}.diag{padding:1rem;border:1px solid #93c5fd;background:#eff6ff;border-radius:16px;line-height:1.65}.steps{display:flex;gap:8px;justify-content:center;margin:1rem 0}.step{padding:.7rem 1.2rem;border-radius:12px;background:#e2e8f0;font-weight:700}.done{background:#bbf7d0}.current{background:#15803d;color:white}.activity{background:white;border:1px solid #dae7de;border-radius:18px;padding:1rem;margin-bottom:12px}.unavailable{opacity:.45}.activity h3{margin:.2rem 0}.effect{width:100%;border-collapse:collapse;font-size:.83rem}.effect td{padding:.55rem;border-bottom:1px solid #e1e8e3;vertical-align:top}.effect td:first-child{width:32%;font-weight:750;color:#14532d;background:#f8fafc}.capital{padding:.5rem;background:#ecfdf5;color:#166534;font-weight:800;border-radius:9px;margin-top:.6rem}@media(max-width:950px){.kpi-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.kpi-grid{grid-template-columns:repeat(2,1fr)}.steps{flex-wrap:wrap}}
</style>""",unsafe_allow_html=True)

def github_ok():return all(str(st.secrets.get(k,"")).strip() for k in ["GITHUB_TOKEN","GITHUB_OWNER","GITHUB_REPO"])
def gh_headers():return {"Authorization":f"Bearer {st.secrets['GITHUB_TOKEN']}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","Cache-Control":"no-cache"}
def gh_url():return f"https://api.github.com/repos/{st.secrets['GITHUB_OWNER']}/{st.secrets['GITHUB_REPO']}/contents/{LEADERBOARD_FILE}"
def branch():return st.secrets.get("GITHUB_BRANCH","main")
def read_board():
 r=requests.get(gh_url(),headers=gh_headers(),params={"ref":branch(),"_":datetime.now().timestamp()},timeout=30)
 if r.status_code==404:return {},None
 r.raise_for_status();x=r.json();return json.loads(base64.b64decode(x["content"]).decode() or "{}"),x["sha"]
def save_shared(rec):
 sid=str(rec["Session ID"]);local=st.session_state.get("local_players",{});local[sid]=rec;st.session_state.local_players=local
 if not github_ok():return
 for _ in range(8):
  rows,sha=read_board();rows[sid]=rec
  body={"message":f"Update leaderboard {rec['Team Name']}","content":base64.b64encode(json.dumps(rows,indent=2).encode()).decode(),"branch":branch()}
  if sha:body["sha"]=sha
  r=requests.put(gh_url(),headers=gh_headers(),json=body,timeout=30)
  if r.status_code in (200,201):return
  if r.status_code not in (409,422):r.raise_for_status()
 raise RuntimeError("Leaderboard busy. Please retry.")
def all_players():
 rows={}
 if github_ok():rows,_=read_board()
 for k,v in st.session_state.get("local_players",{}).items():rows[k]=v
 return list(rows.values())

def initial_state():return {"month":0,"capital_budget":1500.0,"selections":{},"productivity":80.0,"quality":.75,"manufacturing_cost":30.0,"cumulative_profit":0.0,"history":[]}
def calc(state,month,new=None):
 p,q,c=state["productivity"],state["quality"],state["manufacturing_cost"];active=dict(state["selections"])
 if new:active[month]=new
 ages=[];effects=[]
 for activated,name in sorted(active.items()):
  i=month-activated;a=ACTIVITIES[name];dp,dq,dc=a["p"][i],a["q"][i],a["c"][i];p+=dp;q+=dq;c-=dc
  ages.append(f"{name}: Active M{i+1}");effects.append(f"{name}: productivity {dp:+.1f} products/month, quality {dq*100:+.1f} pp, cost {-dc:+.1f}/product")
 q=max(0,min(1,q));c=max(0,c);cap=ACTIVITIES[new]["capital_cost"] if new else 0;good=p*q;landed=(p*c+cap)/good if good else 0;profit=good*50-p*c-cap
 return {"month":month,"productivity":p,"quality":q,"manufacturing_cost":c,"capital_cost":cap,"landed_cost":landed,"monthly_profit":profit,"ages":" | ".join(ages),"effects":" | ".join(effects)}
def record(state,label):
 latest=state["history"][-1] if state["history"] else None
 return {"Session ID":st.session_state.session_id,"Team Name":st.session_state.team_name,"Team Members":st.session_state.team_members,"Month":state["month"],"Selected Activity":label,"Cumulative Profit":state["cumulative_profit"],"Capital Budget Remaining":state["capital_budget"],"Updated At":datetime.now().isoformat(timespec="microseconds"),"Productivity":latest["productivity"] if latest else 80,"Quality %":latest["quality"]*100 if latest else 75,"Manufacturing Cost":latest["manufacturing_cost"] if latest else 30}
def run_month(no_new=False):
 state=st.session_state.state.copy();state["history"]=list(state["history"]);state["selections"]=dict(state["selections"]);m=state["month"]+1;sel=None if no_new else st.session_state.get("selected_activity")
 if not sel and not no_new:st.error("Select one activity.");return
 cap=ACTIVITIES[sel]["capital_cost"] if sel else 0
 if cap>state["capital_budget"]:st.error("Insufficient capital budget.");return
 x=calc(state,m,sel);x["selected"]=sel or "No New Activity - Existing Effects Continue";state["month"]=m;state["capital_budget"]-=cap
 if sel:state["selections"][m]=sel
 state["productivity"],state["quality"],state["manufacturing_cost"]=x["productivity"],x["quality"],x["manufacturing_cost"];state["cumulative_profit"]+=x["monthly_profit"];x["cumulative_profit"]=state["cumulative_profit"];state["history"].append(x);st.session_state.state=state
 try:save_shared(record(state,x["selected"]))
 except Exception as e:st.warning(f"Leaderboard update failed: {e}")
 st.rerun()
def continue_existing():run_month(True)

def hero():st.markdown("<div class='hero'><h1>🏆 Four-Month Profit Optimization Challenge</h1><p>Effects are applied by active month and remain accumulated.</p></div>",unsafe_allow_html=True)
def history_table(state):
 base_profit=80*.75*50-80*30
 rows=[{"Period":"Baseline","Productivity":"80.0 products/month","Quality":"75.0%","Manufacturing Cost":"30.0 /product","Landed Cost":"40.00 /good product","Monthly Profit":f"{base_profit:,.1f}","Cumulative Profit":"0.0"}]
 for h in state["history"]:
  rows.append({"Period":f"Month {h['month']}","Productivity":f"{h['productivity']:.1f} products/month","Quality":f"{h['quality']:.1%}","Manufacturing Cost":f"{h['manufacturing_cost']:.1f} /product","Landed Cost":f"{h['landed_cost']:.2f} /good product","Monthly Profit":f"{h['monthly_profit']:,.1f}","Cumulative Profit":f"{h['cumulative_profit']:,.1f}"})
 for m in range(state["month"]+1,5):rows.append({"Period":f"Month {m}","Productivity":"-","Quality":"-","Manufacturing Cost":"-","Landed Cost":"-","Monthly Profit":"-","Cumulative Profit":"-"})
 rows.append({"Period":"Cumulative","Productivity":"-","Quality":"-","Manufacturing Cost":"-","Landed Cost":"-","Monthly Profit":"-","Cumulative Profit":f"{state['cumulative_profit']:,.1f}"})
 df=pd.DataFrame(rows);st.markdown(df.to_html(index=False,escape=False,classes="summary"),unsafe_allow_html=True)
def performance_graph(state):
 # Baseline plus completed months. Future months are intentionally excluded.
 baseline_profit=80*.75*50-80*30
 periods=["Baseline"]+[f"Month {h['month']}" for h in state["history"]]
 monthly_profit=[baseline_profit]+[h["monthly_profit"] for h in state["history"]]
 cumulative_profit=[0.0]+[h["cumulative_profit"] for h in state["history"]]
 productivity=[80.0]+[h["productivity"] for h in state["history"]]
 quality=[75.0]+[h["quality"]*100 for h in state["history"]]
 manufacturing_cost=[30.0]+[h["manufacturing_cost"] for h in state["history"]]

 fig=go.Figure()
 fig.add_bar(x=periods,y=monthly_profit,name="Monthly Profit",marker_color="#15803d",text=[f"{v:,.1f}" for v in monthly_profit],textposition="outside")
 fig.add_scatter(x=periods,y=cumulative_profit,name="Cumulative Profit",mode="lines+markers+text",text=[f"{v:,.1f}" for v in cumulative_profit],textposition="top center",line=dict(color="#f59e0b",width=3),marker=dict(size=8),yaxis="y")
 fig.update_layout(title="Monthly and Cumulative Profit Trend",xaxis_title="Period",yaxis_title="Profit",legend=dict(orientation="h",yanchor="bottom",y=1.03,xanchor="left",x=0),margin=dict(l=20,r=20,t=85,b=20),height=430,hovermode="x unified")
 st.plotly_chart(fig,use_container_width=True)

 # Three operational KPI trends are shown separately so their units remain clear.
 kpi=go.Figure()
 kpi.add_scatter(x=periods,y=productivity,name="Productivity (products/month)",mode="lines+markers",line=dict(color="#2563eb",width=3))
 kpi.add_scatter(x=periods,y=quality,name="Quality (%)",mode="lines+markers",line=dict(color="#16a34a",width=3))
 kpi.add_scatter(x=periods,y=manufacturing_cost,name="Manufacturing Cost (cost/product)",mode="lines+markers",line=dict(color="#dc2626",width=3))
 kpi.update_layout(title="Operational KPI Trend",xaxis_title="Period",yaxis_title="KPI Value",legend=dict(orientation="h",yanchor="bottom",y=1.03,xanchor="left",x=0),margin=dict(l=20,r=20,t=85,b=20),height=430,hovermode="x unified")
 st.plotly_chart(kpi,use_container_width=True)

def activity_card(name,a,off):
 cls="activity unavailable" if off else "activity";l=a["lines"]
 return f"<div class='{cls}'><div style='font-size:2rem'>{a['icon']}</div><h3>{name}</h3><table class='effect'><tr><td>Productivity<br><small>products/month</small></td><td>{l[0]}</td></tr><tr><td>Quality<br><small>percentage points</small></td><td>{l[1]}</td></tr><tr><td>Manufacturing Cost<br><small>cost/product</small></td><td>{l[2]}</td></tr></table><div class='capital'>Capital Cost: {a['capital_cost']:,.0f}</div></div>"
def leaderboard():
 c1,c2=st.columns([5,1]);c1.subheader("🏅 Live Shared Leaderboard")
 if c2.button("Refresh ↻",use_container_width=True):st.rerun()
 if not github_ok():st.error("Shared storage not connected. Configure GitHub secrets.")
 try:rows=all_players()
 except Exception as e:st.warning(f"Leaderboard refresh failed: {e}");rows=list(st.session_state.get("local_players",{}).values())
 if rows:
  df=pd.DataFrame(rows);df["Cumulative Profit"]=pd.to_numeric(df["Cumulative Profit"],errors="coerce").fillna(0);df=df.sort_values(["Cumulative Profit","Month"],ascending=[False,False]).reset_index(drop=True);df.insert(0,"Rank",range(1,len(df)+1));st.dataframe(df[["Rank","Team Name","Team Members","Month","Selected Activity","Cumulative Profit","Capital Budget Remaining"]],use_container_width=True,hide_index=True)
 else:st.info("Registered players will appear here.")

def registration():
 hero();_,c,_=st.columns([1,1.4,1])
 with c:
  with st.form("reg"):
   st.subheader("Register Your Team");team=st.text_input("Team Name *");members=st.text_area("Team Members *");go=st.form_submit_button("Start Challenge",use_container_width=True)
  if go:
   if not team.strip() or not members.strip():st.error("Enter Team Name and Team Members.")
   else:
    st.session_state.update(registered=True,session_id=str(uuid.uuid4()),team_name=team.strip(),team_members=members.strip(),state=initial_state(),local_players={})
    try:save_shared(record(st.session_state.state,"Registered - Not Started"))
    except Exception as e:st.warning(f"Registration saved locally; shared save failed: {e}")
    st.rerun()
def dashboard():
 hero();state=st.session_state.state
 with st.sidebar:
  st.success(st.session_state.team_name);st.metric("Month",f"{state['month']} / 4");st.metric("Capital Budget",f"{state['capital_budget']:,.0f}");st.metric("Cumulative Profit",f"{state['cumulative_profit']:,.1f}")
  if st.button("Restart"):st.session_state.clear();st.rerun()
 if state["history"]:
  h=state["history"][-1]
  st.markdown(f"<div class='kpi-grid'><div class='kpi'><div class='kl'>Productivity</div><div class='kv'>{h['productivity']:.1f}<span class='ku'>products/month</span></div></div><div class='kpi'><div class='kl'>Quality</div><div class='kv'>{h['quality']:.1%}<span class='ku'>good products</span></div></div><div class='kpi'><div class='kl'>Manufacturing Cost</div><div class='kv'>{h['manufacturing_cost']:.1f}<span class='ku'>cost/product</span></div></div><div class='kpi'><div class='kl'>Landed Cost</div><div class='kv'>{h['landed_cost']:.2f}<span class='ku'>cost/good product</span></div></div><div class='kpi'><div class='kl'>Monthly Profit</div><div class='kv'>{h['monthly_profit']:,.1f}<span class='ku'>per month</span></div></div></div>",unsafe_allow_html=True)
 st.subheader("Month-wise Performance Summary");history_table(state)
 st.subheader("Performance Graphs");performance_graph(state)
 if state["history"]:
  h=state["history"][-1];st.markdown(f"<div class='diag'><b>Active activity age:</b> {h['ages']}<br><b>Increment applied this month:</b> {h['effects']}</div>",unsafe_allow_html=True)
 st.markdown("<div class='steps'>"+"".join(f"<div class='step {'done' if m<=state['month'] else 'current' if m==state['month']+1 else ''}'>Month {m}</div>" for m in range(1,5))+"</div>",unsafe_allow_html=True)
 if state["month"]<4:
  m=state["month"]+1;used=set(state["selections"].values());available=[n for n,a in ACTIVITIES.items() if n not in used and a["capital_cost"]<=state["capital_budget"]];cols=st.columns(2)
  for i,(n,a) in enumerate(ACTIVITIES.items()):
   with cols[i%2]:st.markdown(activity_card(n,a,n in used or a["capital_cost"]>state["capital_budget"]),unsafe_allow_html=True)
  if available:
   sel=st.selectbox(f"Month {m}: Select one activity",available,index=None);st.session_state.selected_activity=sel;st.button(f"Run Month {m}",type="primary",use_container_width=True,disabled=not sel,on_click=run_month)
  else:st.info("No activity is affordable. Existing effects can continue.");st.button(f"Continue to Month {m}",type="primary",use_container_width=True,on_click=continue_existing)
 else:st.success(f"Simulation complete. Cumulative profit: {state['cumulative_profit']:,.1f}")
 leaderboard()

if st.session_state.get("registered"):dashboard()
else:registration()
