import streamlit as st
from datetime import date, datetime, timedelta
from pathlib import Path
import json, os, re

st.set_page_config(page_title="FocusPilot AI", page_icon="🎯", layout="wide", initial_sidebar_state="collapsed")

DATA_FILE = Path("focuspilot_tasks.json")

# ---------- Persistence ----------
def load_tasks():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return [
        {"id": 1, "title": "Finish AI Agent PBL presentation", "category": "Project", "priority": "High",
         "due": str(date.today() + timedelta(days=1)), "minutes": 75, "done": False, "created": datetime.now().isoformat()},
        {"id": 2, "title": "Revise Computer Networks", "category": "Study", "priority": "Medium",
         "due": str(date.today() + timedelta(days=3)), "minutes": 50, "done": False, "created": datetime.now().isoformat()},
        {"id": 3, "title": "Plan weekly workouts", "category": "Personal", "priority": "Low",
         "due": str(date.today() + timedelta(days=2)), "minutes": 20, "done": True, "created": datetime.now().isoformat()},
    ]

def save_tasks():
    DATA_FILE.write_text(json.dumps(st.session_state.tasks, indent=2), encoding="utf-8")

def next_id():
    return max((int(t.get("id", 0)) for t in st.session_state.tasks), default=0) + 1

def parse_natural_task(raw):
    """Offline natural-language parser. Optional LLM improves this through API mode below."""
    text = raw.strip()
    low = text.lower()
    due = date.today() + timedelta(days=3)
    if "today" in low or "tonight" in low:
        due = date.today()
    elif "tomorrow" in low or "by tmr" in low:
        due = date.today() + timedelta(days=1)
    else:
        m = re.search(r"in\s+(\d+)\s+days?", low)
        if m:
            due = date.today() + timedelta(days=int(m.group(1)))
        m = re.search(r"within\s+(\d+)\s+hours?", low)
        if m and int(m.group(1)) <= 12:
            due = date.today()
    mins = 45
    m = re.search(r"(\d+)\s*(?:minutes?|mins?)", low)
    if m:
        mins = max(5, min(600, int(m.group(1))))
    elif re.search(r"\b(2|two)\s*hours?\b", low):
        mins = 120
    elif "hour" in low:
        m = re.search(r"(\d+(?:\.\d+)?)\s*hours?", low)
        if m: mins = max(5, min(600, int(float(m.group(1))*60)))
    priority = "Medium"
    if any(x in low for x in ["urgent", "important", "asap", "exam", "deadline", "high priority", "tomorrow"]):
        priority = "High"
    elif any(x in low for x in ["low priority", "not urgent", "whenever"]):
        priority = "Low"
    category = "Personal"
    if any(x in low for x in ["assignment", "college", "exam", "study", "revise", "notes", "lecture"]):
        category = "Study"
    if any(x in low for x in ["pbl", "project", "presentation", "demo", "prototype", "code"]):
        category = "Project"
    # Remove common scheduling hints to create a readable title
    title = re.sub(r"\b(today|tonight|tomorrow|by tmr|urgent|asap|high priority|low priority|not urgent|whenever)\b", "", text, flags=re.I)
    title = re.sub(r"\b(in|within)\s+\d+\s+(days?|hours?)\b", "", title, flags=re.I)
    title = re.sub(r"\bfor\s+\d+\s*(minutes?|mins?|hours?)\b", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" ,.-")
    title = title[:1].upper() + title[1:] if title else text
    return {"title": title, "category": category, "priority": priority, "due": str(due), "minutes": mins}

def llm_parse(raw, api_key, model, base_url):
    """OpenAI-compatible API integration; user supplies their own key."""
    import requests
    url = (base_url.strip() or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    system = """You convert a user's natural-language productivity request into one task JSON object.
Return ONLY valid JSON with keys title, category, priority, due, minutes.
category must be one of Study, Project, Personal, Health, College, Other.
priority must be Low, Medium, or High.
due must be YYYY-MM-DD. Interpret relative dates from today's date supplied by the user.
minutes must be integer 5..600. Do not invent an exact deadline if none was given; use the provided default date.
Keep title concise and faithful to the request."""
    payload = {
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Today's date is {date.today()}. Default due date is {(date.today()+timedelta(days=3)).isoformat()}. Parse this request: {raw}"}
        ]
    }
    response = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                             json=payload, timeout=30)
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.I)
    result = json.loads(content)
    result["due"] = str(date.fromisoformat(result["due"]))
    result["minutes"] = max(5, min(600, int(result["minutes"])))
    if result.get("priority") not in ["Low", "Medium", "High"]: result["priority"] = "Medium"
    if result.get("category") not in ["Study", "Project", "Personal", "Health", "College", "Other"]: result["category"] = "Other"
    return result

def task_score(task):
    days = (date.fromisoformat(task["due"]) - date.today()).days
    urgency = 5 if days < 0 else 4 if days == 0 else 3 if days == 1 else 2 if days <= 3 else 1
    impact = {"High": 3, "Medium": 2, "Low": 1}.get(task["priority"], 1)
    # Overdue and due-today tasks are boosted. Keep scoring explainable.
    return urgency * 2 + impact

def why_first(task):
    days = (date.fromisoformat(task["due"]) - date.today()).days
    if days < 0: return "Overdue: clear this first or renegotiate the deadline."
    if days == 0: return "Due today: prioritize a focused block now."
    if days == 1: return "Due tomorrow: make meaningful progress today."
    if task["priority"] == "High": return "High priority: protect time for this important outcome."
    if days <= 3: return "Deadline is approaching: schedule it soon."
    return "Can be planned after more urgent work."

# ---------- Session ----------
if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "task_counter" not in st.session_state:
    st.session_state.task_counter = next_id()

# ---------- Style ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {font-family: Inter, sans-serif;}
.main .block-container {max-width: 1120px; padding-top: 1rem; padding-bottom: 5rem;}
.hero {background:linear-gradient(130deg,#111827 0%,#1d4ed8 65%,#6366f1 100%);padding:1.4rem 1.35rem;border-radius:22px;color:#fff;margin-bottom:1rem;box-shadow:0 12px 30px rgba(29,78,216,.18);}
.hero h1 {color:#fff;font-size:clamp(1.7rem,5vw,2.5rem);font-weight:800;letter-spacing:-.04em;margin:0;}
.hero p {color:#dbeafe;margin:.45rem 0 0;font-size:1rem;}
.eyebrow {text-transform:uppercase;letter-spacing:.13em;font-size:.72rem;font-weight:700;color:#bfdbfe;margin-bottom:.4rem;}
.pill {display:inline-block;border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:.25rem .6rem;font-size:.75rem;margin-top:.8rem;color:#eff6ff;}
div[data-testid="stMetric"] {border:1px solid rgba(120,130,150,.22);padding:.75rem;border-radius:16px;background:rgba(120,130,150,.04);}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:16px;}
.stButton button, .stFormSubmitButton button {border-radius:12px;min-height:2.8rem;font-weight:600;}
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {border-radius:12px;}
.small {color:#64748b;font-size:.86rem;}
@media (max-width: 640px) {
 .main .block-container {padding-left:1rem;padding-right:1rem;padding-top:.6rem;}
 .hero {padding:1.15rem;border-radius:18px;}
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
 <div class="eyebrow">Personal productivity copilot</div>
 <h1>🎯 FocusPilot AI</h1>
 <p>Turn messy thoughts into clear next steps. Plan your day with less friction.</p>
 <span class="pill">Natural language · Smart priorities · Focus planning</span>
</div>
""", unsafe_allow_html=True)

with st.expander("🔌 Configure real AI reasoning (optional)", expanded=False):
    st.write("Connect an OpenAI-compatible chat-completions API. If you leave this blank, the demo uses an offline rules-based parser and clearly labels it.")
    api_key = st.text_input("API key", type="password", help="Used only for requests from this app session. Avoid sharing your key or deploying it publicly.")
    model = st.text_input("Model name", value="gpt-4o-mini")
    base_url = st.text_input("API base URL", value="https://api.openai.com/v1", help="For a compatible provider, enter its API base URL.")
    st.caption("For a public deployment, never embed a private API key in source code. Use server-side secrets.")

tasks = st.session_state.tasks
open_tasks = [t for t in tasks if not t["done"]]
done_tasks = [t for t in tasks if t["done"]]
today_tasks = [t for t in open_tasks if date.fromisoformat(t["due"]) == date.today()]
overdue = [t for t in open_tasks if date.fromisoformat(t["due"]) < date.today()]

k1,k2,k3,k4 = st.columns(4)
k1.metric("To do", len(open_tasks))
k2.metric("Completed", len(done_tasks))
k3.metric("Due today", len(today_tasks))
k4.metric("Overdue", len(overdue))

tab_plan, tab_tasks, tab_insights = st.tabs(["✨ AI copilot", "✅ Task board", "📊 Insights"])

with tab_plan:
    st.subheader("Tell your copilot what you need to do")
    st.caption('Example: “Urgent, finish my PBL demo tomorrow for 90 minutes”')
    with st.form("natural_task", clear_on_submit=True):
        natural = st.text_area("Describe a task naturally", placeholder="I need to revise Computer Networks today for 60 minutes; it's urgent.", height=95, label_visibility="collapsed")
        use_ai = st.checkbox("Use connected AI model for parsing", value=bool(api_key), disabled=not bool(api_key))
        submitted = st.form_submit_button("✨ Understand and add task", use_container_width=True)
        if submitted:
            if not natural.strip():
                st.warning("Type a task first.")
            else:
                try:
                    parsed = llm_parse(natural, api_key, model, base_url) if use_ai and api_key else parse_natural_task(natural)
                    parsed.update({"id": next_id(), "done": False, "created": datetime.now().isoformat()})
                    st.session_state.tasks.append(parsed)
                    st.session_state.task_counter = next_id()
                    save_tasks()
                    st.session_state["last_added"] = parsed
                    st.session_state["last_mode"] = "Connected AI model" if use_ai and api_key else "Offline smart parser"
                    st.rerun()
                except Exception as e:
                    st.error(f"AI parsing failed: {e}. Try again or turn off connected AI mode.")
    if "last_added" in st.session_state:
        item = st.session_state.last_added
        mode = st.session_state.get("last_mode", "Offline smart parser")
        st.success(f"Task added using {mode}.")
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.write(f"Priority: **{item['priority']}** · Due: **{item['due']}** · Estimate: **{item['minutes']} min** · Category: **{item['category']}**")
            st.caption("Review extracted details; natural-language interpretation can make mistakes.")
    st.divider()
    st.subheader("Recommended next actions")
    ranked = sorted(open_tasks, key=task_score, reverse=True)
    if not ranked:
        st.success("All clear — add a task and your plan will appear here.")
    else:
        for i, task in enumerate(ranked[:3], 1):
            with st.container(border=True):
                a,b = st.columns([5,1])
                a.markdown(f"**{i}. {task['title']}**")
                a.caption(f"{task['priority']} priority · Due {task['due']} · {task['minutes']} min")
                a.write("🧠 " + why_first(task))
                b.metric("Score", task_score(task))
        st.caption("Transparent score = urgency score × 2 + priority score. It is an explainable heuristic, not hidden AI reasoning.")

    st.divider()
    st.subheader("Build a realistic focus plan")
    available = st.slider("How much focused time do you have today?", 30, 360, 120, step=15)
    break_mins = st.select_slider("Break between focus blocks", options=[5, 10, 15], value=10)
    remaining = available
    planned = []
    for t in ranked:
        block = int(t["minutes"])
        if block <= remaining:
            planned.append(t)
            remaining -= block
        elif not planned:
            planned.append(t)
            remaining = 0
    if planned:
        for n,t in enumerate(planned, 1):
            st.markdown(f"**{n}. {t['title']}** — {t['minutes']} min")
            st.progress(min(1.0, t["minutes"]/max(1, available)))
        total = sum(t["minutes"] for t in planned)
        st.info(f"Plan: {total} minutes of task time. Add {break_mins}-minute breaks between blocks. {max(0, len(open_tasks)-len(planned))} task(s) remain outside this plan.")
    else:
        st.write("Add a task to create a focus plan.")

with tab_tasks:
    st.subheader("Your task board")
    filt = st.segmented_control("Filter", ["All", "Open", "Done", "Overdue"], default="Open", selection_mode="single")
    shown = sorted(tasks, key=task_score, reverse=True)
    if filt == "Open": shown = [t for t in shown if not t["done"]]
    elif filt == "Done": shown = [t for t in shown if t["done"]]
    elif filt == "Overdue": shown = [t for t in shown if not t["done"] and date.fromisoformat(t["due"]) < date.today()]
    if not shown:
        st.info("No tasks in this view.")
    for task in shown:
        with st.container(border=True):
            c1,c2 = st.columns([5,1])
            with c1:
                st.markdown(("~~"+task["title"]+"~~") if task["done"] else f"**{task['title']}**")
                st.caption(f"{task['category']} · {task['priority']} priority · {task['due']} · {task['minutes']} min")
                if not task["done"]: st.write(why_first(task))
            with c2:
                checked = st.checkbox("Done", value=task["done"], key=f"done_{task['id']}")
                if checked != task["done"]:
                    task["done"] = checked
                    save_tasks()
                    st.rerun()
                if st.button("Delete", key=f"delete_{task['id']}"):
                    st.session_state.tasks = [t for t in st.session_state.tasks if t["id"] != task["id"]]
                    save_tasks()
                    st.rerun()
    with st.expander("＋ Add task with detailed fields"):
        with st.form("manual_add", clear_on_submit=True):
            title = st.text_input("Task title")
            c,d = st.columns(2)
            category = c.selectbox("Category", ["Study","Project","Personal","Health","College","Other"])
            priority = d.selectbox("Priority", ["High","Medium","Low"], index=1)
            due = st.date_input("Due date", value=date.today()+timedelta(days=1))
            minutes = st.number_input("Minutes", min_value=5, max_value=600, value=45, step=5)
            if st.form_submit_button("Add task", use_container_width=True):
                if title.strip():
                    st.session_state.tasks.append({"id":next_id(),"title":title.strip(),"category":category,"priority":priority,"due":str(due),"minutes":int(minutes),"done":False,"created":datetime.now().isoformat()})
                    save_tasks()
                    st.rerun()
                else: st.warning("Enter a task title.")

with tab_insights:
    st.subheader("Your productivity snapshot")
    total = len(tasks)
    rate = round(100*len(done_tasks)/total) if total else 0
    a,b = st.columns(2)
    a.metric("Completion rate", f"{rate}%")
    b.metric("Open workload", f"{sum(t['minutes'] for t in open_tasks)} min")
    st.progress(rate/100 if total else 0)
    for p in ["High","Medium","Low"]:
        count = sum(1 for t in open_tasks if t["priority"] == p)
        st.write(f"**{p} priority** · {count} open task(s)")
    st.caption("Data is saved to a local JSON file when running on your own computer. Hosted sessions may have different persistence guarantees.")

st.divider()
with st.expander("ℹ️ Project architecture & limitations"):
    st.markdown("""
**Current prototype**
- Streamlit responsive web app designed to open in an Android browser.
- Natural-language task parsing through either a connected OpenAI-compatible model or an offline heuristic parser.
- Explainable deadline/priority scoring and a time-budget planner.
- Local JSON persistence on the computer running the app.

**Not included yet**
- Android APK, calendar sync, push notifications, authentication, multi-user database, or a background autonomous agent.
- Edge computing is a future extension; this version does not claim to run an LLM on-device.

**Suggested next steps for the PBL**
1. Add a secure backend and database.
2. Add calendar/reminder integrations with user consent.
3. Evaluate task extraction accuracy on a small test set.
4. Explore Ollama on a laptop or a compact on-device model for privacy-oriented edge inference.
""")
st.caption("FocusPilot AI · Educational prototype · Review all AI-extracted task details before relying on them.")
