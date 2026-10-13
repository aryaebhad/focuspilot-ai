
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="FocusPilot AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DATA_FILE = Path("focuspilot_tasks.json")


def default_tasks():
    return [
        {
            "id": 1,
            "title": "Finish AI Agent PBL presentation",
            "category": "Project",
            "priority": "High",
            "due": str(date.today() + timedelta(days=1)),
            "minutes": 75,
            "done": False,
        },
        {
            "id": 2,
            "title": "Revise Computer Networks",
            "category": "Study",
            "priority": "Medium",
            "due": str(date.today() + timedelta(days=2)),
            "minutes": 50,
            "done": False,
        },
        {
            "id": 3,
            "title": "Plan weekly workouts",
            "category": "Personal",
            "priority": "Low",
            "due": str(date.today() + timedelta(days=3)),
            "minutes": 20,
            "done": False,
        },
    ]


def load_tasks():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (ValueError, OSError):
            pass
    return default_tasks()


if "tasks" not in st.session_state:
    st.session_state.tasks = load_tasks()

if "next_id" not in st.session_state:
    st.session_state.next_id = max(
        (int(t.get("id", 0)) for t in st.session_state.tasks),
        default=0,
    ) + 1

if "focus" not in st.session_state:
    st.session_state.focus = None

if "last_alert" not in st.session_state:
    st.session_state.last_alert = None


def save_tasks():
    try:
        DATA_FILE.write_text(
            json.dumps(st.session_state.tasks, indent=2),
            encoding="utf-8",
        )
    except OSError:
        st.warning("Tasks could not be saved to this hosting session.")


def parse_task(raw):
    text = raw.strip()
    low = text.lower()

    due = date.today() + timedelta(days=3)

    if "day after tomorrow" in low:
        due = date.today() + timedelta(days=2)
    elif "tomorrow" in low or "kal" in low:
        due = date.today() + timedelta(days=1)
    elif "today" in low or "aaj" in low:
        due = date.today()

    duration = 45
    m = re.search(r"(\d+)\s*(minutes?|mins?|min)\b", low)
    if m:
        duration = max(5, min(600, int(m.group(1))))
    else:
        h = re.search(r"(\d+)\s*hours?\b", low)
        if h:
            duration = max(5, min(600, int(h.group(1)) * 60))

    priority = "Medium"
    if any(w in low for w in ["urgent", "important", "asap", "high priority"]):
        priority = "High"
    elif any(w in low for w in ["low priority", "not urgent"]):
        priority = "Low"

    category = "Personal"
    if any(w in low for w in ["study", "revise", "exam", "cn ", "computer networks"]):
        category = "Study"
    elif any(w in low for w in ["pbl", "project", "presentation", "demo", "assignment"]):
        category = "Project"
    elif any(w in low for w in ["workout", "gym", "exercise"]):
        category = "Health"

    title = re.sub(
        r"\b(today|tomorrow|kal|aaj|urgent|important|asap|"
        r"\d+\s*(minutes?|mins?|min|hours?|hrs?))\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    title = re.sub(r"\s+", " ", title).strip(" ,.-")
    title = title[:1].upper() + title[1:] if title else text

    return {
        "title": title,
        "category": category,
        "priority": priority,
        "due": str(due),
        "minutes": duration,
        "done": False,
    }


def score(task):
    priority_points = {"High": 30, "Medium": 20, "Low": 10}
    try:
        days_left = (date.fromisoformat(task["due"]) - date.today()).days
    except (ValueError, KeyError):
        days_left = 3

    urgency = 25 if days_left < 0 else 20 if days_left == 0 else 10 if days_left == 1 else 0
    return priority_points.get(task.get("priority"), 10) + urgency


def finish_task(task_id):
    for task in st.session_state.tasks:
        if task["id"] == task_id:
            task["done"] = True
            break
    save_tasks()


st.markdown(
    """
    <div style="padding:26px;border-radius:22px;
    background:linear-gradient(120deg,#13214b,#315cf4,#6756df);
    color:white;">
    <div style="letter-spacing:3px;font-size:12px;font-weight:700;">
    PERSONAL PRODUCTIVITY COPILOT
    </div>
    <h1>🎯 FocusPilot AI</h1>
    <p style="font-size:18px;">
    Turn messy thoughts into clear next steps. Plan your day with less friction.
    </p>
    <p>Natural-language tasks · Smart priorities · Focus sessions</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Educational PBL prototype · Review AI-extracted task details before relying on them.")

tasks = st.session_state.tasks
open_tasks = [t for t in tasks if not t.get("done", False)]
completed_tasks = [t for t in tasks if t.get("done", False)]
overdue_tasks = [
    t for t in open_tasks
    if t.get("due", "9999-12-31") < str(date.today())
]

m1, m2, m3, m4 = st.columns(4)
m1.metric("To do", len(open_tasks))
m2.metric("Completed", len(completed_tasks))
m3.metric("Due today", sum(t.get("due") == str(date.today()) for t in open_tasks))
m4.metric("Overdue", len(overdue_tasks))

tab_ai, tab_board, tab_focus, tab_insights = st.tabs(
    ["✨ AI Copilot", "✅ Task board", "🔒 Focus Lock", "📊 Insights"]
)

with tab_ai:
    st.subheader("Tell your copilot what you need to do")
    st.write('Example: "Urgent, finish my PBL demo tomorrow for 60 minutes."')

    with st.form("add_task_form"):
        raw = st.text_area(
            "Describe your task",
            placeholder="I need to revise Computer Networks tomorrow for 60 minutes; it's urgent.",
        )
        submitted = st.form_submit_button("✨ Understand and add task", use_container_width=True)

    if submitted:
        if not raw.strip():
            st.warning("Enter a task first.")
        else:
            parsed = parse_task(raw)
            parsed["id"] = st.session_state.next_id
            st.session_state.next_id += 1
            st.session_state.tasks.append(parsed)
            save_tasks()
            st.success("Task added. Review its title, priority and deadline below.")
            st.rerun()

    st.markdown("#### Recommended next actions")
    ranked = sorted(open_tasks, key=score, reverse=True)
    if ranked:
        for task in ranked[:3]:
            st.write(
                f"**{task['title']}** — {task['priority']} priority · "
                f"{task['minutes']} min · due {task['due']}"
            )
    else:
        st.success("All clear! Add a task when you're ready.")

with tab_board:
    st.subheader("Your task board")
    filter_choice = st.radio(
        "Filter",
        ["All", "Open", "Done", "Overdue"],
        horizontal=True,
    )

    for task in list(st.session_state.tasks):
        is_done = task.get("done", False)
        is_overdue = not is_done and task.get("due", "9999-12-31") < str(date.today())

        if filter_choice == "Open" and is_done:
            continue
        if filter_choice == "Done" and not is_done:
            continue
        if filter_choice == "Overdue" and not is_overdue:
            continue

        with st.container(border=True):
            title = task.get("title", "Untitled task")
            st.markdown(f"### {'~~' + title + '~~' if is_done else title}")
            st.write(
                f"{task.get('category', 'Personal')} · "
                f"{task.get('priority', 'Medium')} priority · "
                f"Due {task.get('due', 'Not set')} · "
                f"{task.get('minutes', 30)} min"
            )

            c1, c2, c3 = st.columns(3)

            if not is_done:
                if c1.button("✓ Complete", key=f"done_{task['id']}"):
                    finish_task(task["id"])
                    st.rerun()

                if c2.button("🔒 Focus", key=f"focus_{task['id']}"):
                    st.session_state.focus = {
                        "task_id": task["id"],
                        "started": None,
                        "duration": int(task.get("minutes", 25)) * 60,
                        "active": False,
                    }
                    st.rerun()

            if c3.button("🗑️ Delete", key=f"delete_{task['id']}"):
                st.session_state.tasks = [
                    t for t in st.session_state.tasks if t["id"] != task["id"]
                ]
                save_tasks()
                st.rerun()

with tab_focus:
    st.subheader("🔒 Focus Lock")
    st.write(
        "Choose a task, start a focus session, and keep your attention on one goal."
    )

    current_focus = st.session_state.focus

    if current_focus is None:
        available = [t for t in open_tasks]
        if available:
            selected = st.selectbox(
                "Choose a task",
                available,
                format_func=lambda t: t["title"],
            )
            minutes = st.slider("Focus duration (minutes)", 1, 120, 25)
            if st.button("Start focus session", use_container_width=True):
                st.session_state.focus = {
                    "task_id": selected["id"],
                    "started": time.time(),
                    "duration": minutes * 60,
                    "active": True,
                }
                st.rerun()
        else:
            st.info("Add an open task to start focusing.")

    else:
        task = next(
            (t for t in st.session_state.tasks if t["id"] == current_focus["task_id"]),
            None,
        )

        if task is None:
            st.session_state.focus = None
            st.rerun()

        elif not current_focus["active"]:
            st.info(f"Selected task: {task['title']}")
            if st.button("Start this focus session", use_container_width=True):
                current_focus["started"] = time.time()
                current_focus["active"] = True
                st.rerun()
            if st.button("Cancel selection"):
                st.session_state.focus = None
                st.rerun()

        else:
            st_autorefresh(interval=1000, key="focus_timer_refresh")
            elapsed = int(time.time() - current_focus["started"])
            remaining = max(0, current_focus["duration"] - elapsed)
            mins, secs = divmod(remaining, 60)

            st.markdown(f"### {task['title']}")
            st.metric("Time remaining", f"{mins:02d}:{secs:02d}")
            st.progress(
                min(1.0, elapsed / max(1, current_focus["duration"]))
            )
            st.info("Focus Lock is active inside this web app.")

            if remaining <= 0:
                st.session_state.last_alert = task["id"]
                st.warning("⏰ Focus session finished! Take a break or complete your task.")
                if st.button("✓ Task completed — unlock"):
                    finish_task(task["id"])
                    st.session_state.focus = None
                    st.rerun()
                if st.button("End session without completing"):
                    st.session_state.focus = None
                    st.rerun()
            else:
                if st.button("End session early"):
                    st.session_state.focus = None
                    st.rerun()

    st.caption(
        "Demo limitation: this web app cannot block other Android apps or guarantee "
        "background alarms when the browser is closed."
    )

with tab_insights:
    st.subheader("Your productivity snapshot")
    total = len(st.session_state.tasks)
    done = sum(t.get("done", False) for t in st.session_state.tasks)
    completion = round(done / total * 100) if total else 0
    workload = sum(t.get("minutes", 0) for t in open_tasks)

    a, b = st.columns(2)
    a.metric("Completion rate", f"{completion}%")
    b.metric("Open workload", f"{workload} min")
    st.progress(completion / 100 if total else 0)

    for level in ["High", "Medium", "Low"]:
        count = sum(
            t.get("priority") == level and not t.get("done", False)
            for t in st.session_state.tasks
        )
        st.write(f"**{level} priority:** {count} open task(s)")

    st.caption(
        "Tasks are stored in a local JSON file in this app's runtime. "
        "Hosted sessions may not preserve data permanently."
    )
