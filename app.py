import base64, io, json, uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

st.set_page_config(page_title="Profit Optimization Challenge",page_icon="🏆",layout="wide",initial_sidebar_state="expanded")
MODEL=json.loads(Path("config/model.json").read_text());BASE=MODEL["baseline"];ACT=MODEL["activities"]
LB_PATH="data/leaderboard.csv";LOG_PATH="data/simulation_log.csv"
LB_COLS=["Session ID","Team Name","Team Members","Year","Productivity","Quality %","Landed Cost","Selling Price","Annual Net Profit","Cumulative Net Profit","Budget Remaining","Eligible Score","Updated At"]
LOG_COLS=["Session ID","Team Name","Team Members","Year","Activity 1","Activity 2","Deployment Counts","Productivity","Quality %","Manufacturing Cost","Investment","Landed Cost","Selling Price","Annual Net Profit","Cumulative Net Profit","Budget Remaining","Diagnosis","Created At"]

st.markdown("""<style>
.stApp{background:radial-gradient(circle at 8% 4%,#dcfce7 0,transparent 22%),linear-gradient(135deg,#f8fffa,#eef7f0)}.block-container{max-width:1320px;padding-top:1.1rem;padding-bottom:3rem}#MainMenu,footer{visibility:hidden}.hero{padding:1.8rem 2rem;border-radius:25px;background:linear-gradient(125deg,#103d27,#166534 52%,#16a34a);color:#fff;box-shadow:0 18px 48px rgba(20,83,45,.2);margin-bottom:1rem}.hero h1{margin:0}.hero p{margin:.4rem 0 0;opacity:.9}.baseline{padding:1rem;border-radius:16px;background:#ecfeff;border:1px solid #67e8f9;margin:.8rem 0}.activity{background:#fff;border:1px solid #d9e8de;border-radius:17px;padding:.9rem;height:100%;box-shadow:0 8px 22px rgba(20,83,45,.07)}.activity.locked{opacity:.42;filter:grayscale(.8)}.activity .ico{font-size:2rem}.activity h4{margin:.25rem 0}.activity p{font-size:.84rem;color:#64748b;margin:.2rem 0}.impact{margin-top:.55rem;padding:.55rem;border-radius:10px;background:#f8fafc;border:1px solid #dbe5df;font-size:.8rem}.gain{color:#166534;font-weight:700}.loss{color:#b91c1c;font-weight:700}.neutral{color:#475569;font-weight:700}.insight{padding:.9rem 1rem;border-radius:14px;background:#eff6ff;border:1px solid #93c5fd;margin:.7rem 0}.yearbox{padding:1rem;border-radius:16px;background:#fff7ed;border:1px solid #fdba74;margin:.8rem 0}.process-wrap{background:#fff;border:1px solid #b9d8c1;border-radius:22px;padding:1rem;overflow-x:auto}.process-line{min-width:1000px;display:flex;align-items:center;gap:10px;position:relative;padding:20px 10px 48px}.unit{width:145px;min-height:80px;border:2px solid #15803d;border-radius:13px;background:#eefbf1;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;font-weight:750}.unit span{font-size:1.8rem}.arrow{width:48px;height:12px;background:#15803d;position:relative}.arrow:after{content:"";position:absolute;right:-13px;top:-7px;border-left:14px solid #15803d;border-top:13px solid transparent;border-bottom:13px solid transparent}.belt{position:absolute;left:15px;right:15px;bottom:18px;height:10px;border-radius:6px;background:repeating-linear-gradient(90deg,#14532d 0 24px,#86efac 24px 38px);animation:belt .75s linear infinite}.tile{position:absolute;bottom:29px;width:34px;height:20px;background:#f59e0b;border:2px solid #9a5a06;border-radius:3px;animation:move 8s linear infinite}.tile.t2{animation-delay:-2.7s}.tile.t3{animation-delay:-5.4s}@keyframes belt{to{background-position:38px 0}}@keyframes move{0%{left:2%}100%{left:95%}}.stButton>button,.stFormSubmitButton>button{border-radius:12px;min-height:45px;font-weight:700}.stFormSubmitButton>button{background:#15803d!important;color:#fff!important;border:0!important}</style>""",unsafe_allow_html=True)

def gh_ok():return all(str(st.secrets.get(k,"")).strip() for k in ["GITHUB_TOKEN","GITHUB_OWNER","GITHUB_REPO"])
def gh_headers():return {"Authorization":f"Bearer {st.secrets['GITHUB_TOKEN']}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
def gh_url(path):return f"https://api.github.com/repos/{st.secrets['GITHUB_OWNER']}/{st.secrets['GITHUB_REPO']}/contents/{path}"
def read_csv(path,cols):
 r=requests.get(gh_url(path),headers=gh_headers(),params={"ref":st.secrets.get("GITHUB_BRANCH","main")},timeout=30)
 if r.status_code==404:return pd.DataFrame(columns=cols),None
 r.raise_for_status();p=r.json()
 try:df=pd.read_csv(io.BytesIO(base64.b64decode(p["content"])))
 except pd.errors.EmptyDataError:df=pd.DataFrame(columns=cols)
 for c in cols:
  if c not in df:df[c]=""
 return df[cols],p["sha"]
def write_csv(path,df,cols,sha,msg):
 body={"message":msg,"content":base64.b64encode(df[cols].to_csv(index=False).encode()).decode(),"branch":st.secrets.get("GITHUB_BRANCH","main")}
 if sha:body["sha"]=sha
 r=requests.put(gh_url(path),headers=gh_headers(),json=body,timeout=30);r.raise_for_status()
def append_csv(path,row,cols,msg):
 df,sha=read_csv(path,cols);df=pd.concat([df,pd.DataFrame([row])],ignore_index=True);write_csv(path,df,cols,sha,msg)
def update_lb(row):
 if gh_ok():
  df,sha=read_csv(LB_PATH,LB_COLS);df=df[~df["Session ID"].astype(str).eq(row["Session ID"])];df=pd.concat([df,pd.DataFrame([row])],ignore_index=True);write_csv(LB_PATH,df,LB_COLS,sha,"Update leaderboard")
 local=st.session_state.get("local_lb",pd.DataFrame(columns=LB_COLS));local=local[~local["Session ID"].astype(str).eq(row["Session ID"])];st.session_state.local_lb=pd.concat([local,pd.DataFrame([row])],ignore_index=True)
def get_lb():
 if gh_ok():
  try:return read_csv(LB_PATH,LB_COLS)[0]
  except Exception as e:st.caption(f"Shared leaderboard unavailable: {e}")
 return st.session_state.get("local_lb",pd.DataFrame(columns=LB_COLS))

def hero():st.markdown("<div class='hero'><h1>🏆 Four-Year Profit Optimization Challenge</h1><p>Deploy two activities in Years 1–3 and at least one in Year 4. Spend the full budget and maximize profit.</p></div>",unsafe_allow_html=True)
def conveyor(p):
 speed=max(2.7,min(14,900/max(p,1)));st.markdown(f"""<div class='process-wrap'><div class='process-line'><div class='unit'><span>🧱</span>Inputs</div><div class='arrow'></div><div class='unit'><span>🏭</span>Production</div><div class='arrow'></div><div class='unit'><span>✅</span>Quality</div><div class='arrow'></div><div class='unit'><span>🚚</span>Landed Cost</div><div class='arrow'></div><div class='unit'><span>💰</span>Profit</div><div class='belt'></div><div class='tile' style='animation-duration:{speed}s'></div><div class='tile t2' style='animation-duration:{speed}s'></div><div class='tile t3' style='animation-duration:{speed}s'></div></div></div>""",unsafe_allow_html=True)
def initial():return {"year":0,"budget":100.0,"p":80.0,"q":.75,"c":30.0,"cum":0.0,"counts":{},"history":[]}
def multiplier(count):return MODEL["repeat_multipliers"][min(count,2)]
def effect(name,year,count):
 a=ACT[name];m=multiplier(count);i=year-1
 return {"p":a["productivity_gain"][i]*m,"q":a["quality_gain"][i]*m,"c":a["cost_reduction"][i]*m,"m":m}
def diagnosis(m,year,previous=None):
 b=MODEL["optimal_benchmark"][f"year_{year}"];parts=[]
 for label,key,target,higher in [("Productivity","p",b["productivity"],True),("Quality","q",b["quality"],True),("Manufacturing cost","c",b["manufacturing_cost"],False)]:
  actual=m[key];good=actual>=target if higher else actual<=target;parts.append(f"{'Gaining' if good else 'Lacking'}: {label} {actual:.2f} vs benchmark {target:.2f}.")
 if previous:
  d=m["profit"]-previous["profit"];parts.append(f"Annual net profit {'increased' if d>=0 else 'decreased'} by {abs(d):.2f}.")
 return " ".join(parts)
def run_year():
 s=st.session_state.state.copy();year=s["year"]+1;a1=st.session_state.get("sel1","None");a2=st.session_state.get("sel2","None");selected=[a for a in [a1,a2] if a!="None"]
 required=2 if year<=3 else 1
 if len(selected)<required:st.error(f"Year {year} requires at least {required} selected activit{'ies' if required>1 else 'y'}.");return
 if len(set(selected))!=len(selected):st.error("Select different activities in the same year.");return
 spend=sum(ACT[a]["investment"] for a in selected)
 if spend>s["budget"]:st.error("Selected activities exceed the remaining budget.");return
 counts=dict(s["counts"]);effects=[]
 for a in selected:
  e=effect(a,year,counts.get(a,0));effects.append(e);counts[a]=counts.get(a,0)+1
 p=s["p"]+sum(e["p"] for e in effects);q=max(0,min(1,s["q"]+sum(e["q"] for e in effects)));c=max(0,s["c"]-sum(e["c"] for e in effects));good=p*q;landed=(p*c+spend)/good;profit=good*MODEL["selling_price"]-p*c-spend
 m={"year":year,"p":p,"q":q,"c":c,"landed":landed,"profit":profit,"investment":spend,"selected":selected};m["diagnosis"]=diagnosis(m,year,s["history"][-1] if s["history"] else None)
 s.update(year=year,budget=s["budget"]-spend,p=p,q=q,c=c,cum=s["cum"]+profit,counts=counts);s["history"].append(m);st.session_state.state=s
 eligible=s["cum"] if year==4 and s["budget"]==0 else s["cum"]-(s["budget"]*100 if year==4 else 0)
 row={"Session ID":st.session_state.sid,"Team Name":st.session_state.team,"Team Members":st.session_state.members,"Year":year,"Productivity":p,"Quality %":q*100,"Landed Cost":landed,"Selling Price":MODEL["selling_price"],"Annual Net Profit":profit,"Cumulative Net Profit":s["cum"],"Budget Remaining":s["budget"],"Eligible Score":eligible,"Updated At":datetime.now().strftime("%Y-%m-%d %H:%M:%S")};update_lb(row)
 if gh_ok():
  log={"Session ID":st.session_state.sid,"Team Name":st.session_state.team,"Team Members":st.session_state.members,"Year":year,"Activity 1":a1,"Activity 2":a2,"Deployment Counts":" | ".join(f"{k}:{v}" for k,v in counts.items()),"Productivity":p,"Quality %":q*100,"Manufacturing Cost":c,"Investment":spend,"Landed Cost":landed,"Selling Price":MODEL["selling_price"],"Annual Net Profit":profit,"Cumulative Net Profit":s["cum"],"Budget Remaining":s["budget"],"Diagnosis":m["diagnosis"],"Created At":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
  try:append_csv(LOG_PATH,log,LOG_COLS,f"Add Year {year}")
  except Exception as e:st.warning(f"Year completed; GitHub save failed: {e}")
 st.rerun()
def impact(name,year,count):
 e=effect(name,year,count);lines=[]
 for label,v,unit,positive in [("Productivity",e["p"]," tiles/day",True),("Quality",e["q"]*100," pp",True),("Manufacturing cost",-e["c"],"/tile",False)]:
  good=v>0 if positive else v<0;kind="gain" if good else "loss" if v else "neutral";arrow="▲" if kind=="gain" else "▼" if kind=="loss" else "•";lines.append(f"<div class='{kind}'>{arrow} {label}: {v:+.2f}{unit}</div>" if v else f"<div class='neutral'>• {label}: no change</div>")
 return "".join(lines),e["m"]
def registration():
 hero();conveyor(80);_,c,_=st.columns([1,1.5,1])
 with c:
  with st.form("reg"):
   team=st.text_input("Team Name *");members=st.text_area("Team Members *");ok=st.form_submit_button("Start Challenge →",use_container_width=True)
  if ok:
   if not team.strip() or not members.strip():st.error("Enter both fields.")
   else:st.session_state.update(registered=True,sid=str(uuid.uuid4()),team=team.strip(),members=members.strip(),state=initial(),local_lb=pd.DataFrame(columns=LB_COLS));st.rerun()
def cards(s,year):
 cols=st.columns(3)
 for i,(name,a) in enumerate(ACT.items()):
  count=s["counts"].get(name,0);html,m=impact(name,year,count);locked=a["investment"]>s["budget"] or count>=3
  with cols[i%3]:st.markdown(f"<div class='activity{' locked' if locked else ''}'><div class='ico'>{a['icon']}</div><h4>{name}</h4><p>Deployment {count+1}; effectiveness {m:.0%}</p><div class='impact'>{html}</div><p><b>Budget: {a['investment']}</b></p></div>",unsafe_allow_html=True)
 available=[a for a in ACT if ACT[a]["investment"]<=s["budget"] and s["counts"].get(a,0)<3];left,right=st.columns(2);a1=left.selectbox("Activity 1",["None"]+available,key=f"a1_{year}");remaining=s["budget"]-(ACT[a1]["investment"] if a1!="None" else 0);a2opts=[a for a in available if a!=a1 and ACT[a]["investment"]<=remaining];a2=right.selectbox("Activity 2",["None"]+a2opts,key=f"a2_{year}");st.session_state.sel1=a1;st.session_state.sel2=a2;selected=[a for a in [a1,a2] if a!="None"];spend=sum(ACT[a]["investment"] for a in selected);x,y,z=st.columns(3);x.metric("Budget",f"{s['budget']:.0f}");y.metric("Selected",f"{spend:.0f}");z.metric("After",f"{s['budget']-spend:.0f}");required=2 if year<=3 else 1;st.caption(f"Selection requirement: {'exactly 2' if year<=3 else 'at least 1'} activity/activities.");st.button(f"Run Year {year} ▶",type="primary",use_container_width=True,disabled=len(selected)<required,on_click=run_year)
def trend(history):
 df=pd.DataFrame(history);x=[f"Year {y}" for y in df.year];fig=go.Figure();fig.add_bar(x=x,y=df.profit,name="Net Profit",marker_color="#15803d");fig.add_scatter(x=x,y=df.landed,name="Landed Cost",yaxis="y2",mode="lines+markers",line=dict(color="#f59e0b"));fig.update_layout(title="Profit and Landed Cost",yaxis2=dict(overlaying="y",side="right",title="Landed Cost"));st.plotly_chart(fig,use_container_width=True)
def leaderboard():
 st.subheader("🏅 Live Leaderboard");lb=get_lb()
 if lb.empty:st.info("Complete a year to populate the leaderboard.");return
 for c in ["Eligible Score","Cumulative Net Profit","Budget Remaining"]:lb[c]=pd.to_numeric(lb[c],errors="coerce")
 lb=lb.sort_values(["Eligible Score","Cumulative Net Profit"],ascending=False).reset_index(drop=True);lb.insert(0,"Rank",range(1,len(lb)+1));st.dataframe(lb[["Rank","Team Name","Team Members","Year","Cumulative Net Profit","Budget Remaining","Eligible Score"]],use_container_width=True,hide_index=True)
def dashboard():
 hero();s=st.session_state.state;conveyor(s["p"])
 with st.sidebar:
  st.success(st.session_state.team);st.write(st.session_state.members);st.metric("Year",f"{s['year']} / 4");st.metric("Budget",f"{s['budget']:.0f}");st.metric("Cumulative Profit",f"{s['cum']:.2f}")
  if st.button("Restart",use_container_width=True):st.session_state.clear();st.rerun()
 if not s["history"]:st.markdown("<div class='baseline'><h3>Year 0 Fixed Baseline</h3><p>Productivity 80 | Quality 75% | Manufacturing cost 30/tile | Selling price 50/tile</p></div>",unsafe_allow_html=True)
 else:
  r=s["history"][-1];a,b,c,d,e=st.columns(5);a.metric("Productivity",f"{r['p']:.1f}");b.metric("Quality",f"{r['q']:.1%}");c.metric("Landed Cost",f"{r['landed']:.2f}");d.metric("Selling Price",f"{MODEL['selling_price']:.2f}");e.metric("Annual Profit",f"{r['profit']:.2f}");st.markdown(f"<div class='insight'><b>Year {s['year']} diagnosis:</b> {r['diagnosis']}</div>",unsafe_allow_html=True);trend(s["history"])
 with st.expander("📋 Full year-by-year effect matrix"):
  rows=[]
  for a,d in ACT.items():
   for y in range(1,5):rows.append({"Activity":a,"Year":y,"Productivity Gain":d["productivity_gain"][y-1],"Quality Gain (pp)":d["quality_gain"][y-1]*100,"Manufacturing Cost Reduction":d["cost_reduction"][y-1],"Budget":d["investment"]})
  st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
 with st.expander("📐 Model logic"):
  st.markdown("""Each selected activity changes the current process state. Repeating the same activity is allowed as a new annual improvement wave, with diminishing returns: first deployment 100%, second 40%, third 15%.\n\n```text\nP_y = P_(y-1) + Σ ProductivityGain(activity,y) × RepeatMultiplier\nQ_y = MIN(100%, Q_(y-1) + Σ QualityGain(activity,y) × RepeatMultiplier)\nC_y = MAX(0, C_(y-1) - Σ CostReduction(activity,y) × RepeatMultiplier)\nGood Tiles = P_y × Q_y\nLanded Cost = (P_y × C_y + Annual Investment) / Good Tiles\nAnnual Profit = Good Tiles × Selling Price - P_y × C_y - Annual Investment\n```""")
 if s["year"]<4:
  year=s["year"]+1;st.markdown(f"<div class='yearbox'><h3>Year {year} Decision</h3><p>{'Select exactly two activities.' if year<=3 else 'Select at least one activity.'}</p></div>",unsafe_allow_html=True);cards(s,year)
 else:
  if s["budget"]==0:st.success(f"Challenge complete. Full budget used. Cumulative profit: {s['cum']:.2f}")
  else:st.warning(f"Challenge complete with {s['budget']:.0f} unspent. Eligible score includes a penalty.")
 leaderboard()

if st.session_state.get("registered"):dashboard()
else:registration()
