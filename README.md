# FocusPilot AI — Advanced PBL Demo

A mobile-friendly Streamlit web app for **AI Agent for Personal Productivity Enhancement**.

## What it does
- Natural-language task entry (e.g. “Urgent, revise CN tomorrow for 60 minutes”).
- Optional real model integration through an OpenAI-compatible Chat Completions API.
- Offline fallback parser when no API is configured.
- Explainable deadline/priority ranking and focus-time planning.
- Task completion, filtering, delete controls, insights and local JSON persistence.

## Run on a Windows laptop
Install Python 3.10+ from https://www.python.org/downloads/

Open Command Prompt in this folder and run:
```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```
Open the local URL printed by Streamlit, usually http://localhost:8501.

## Use it on Android
The app is a responsive web app, not an APK. Easiest path:
1. Run it on a laptop on the same Wi-Fi as your Android phone.
2. Start Streamlit with:
   `python -m streamlit run app.py --server.address 0.0.0.0`
3. Find your laptop's local IPv4 address (`ipconfig` on Windows).
4. On Android, open `http://LAPTOP-IP:8501`.
5. Allow Streamlit through Windows Firewall on your private network if asked.

For a faculty demo accessible anywhere, deploy to a hosting service. Do not put an API key in public source code. Use the host's secret manager.

## Configure real AI reasoning
Expand “Configure real AI reasoning” in the app and enter:
- API key from your chosen provider
- Model name
- API base URL (defaults to OpenAI-compatible `https://api.openai.com/v1`)

The app calls the provider's `/chat/completions` endpoint. API costs, availability and model support depend on your provider. Never share your key or deploy it publicly. If no key is supplied, the app uses a simple offline parser and tells you which mode was used.

## Suggested demo script (3 minutes)
1. Show the four summary metrics.
2. Enter: “Urgent, finish my PBL presentation tomorrow for 90 minutes.”
3. Review the parsed title, priority, deadline and estimate.
4. Show recommended next actions and the focus-time plan.
5. Mark a task complete; show the completion rate in Insights.
6. Explain the transparent heuristic and discuss LLM integration and edge computing as current/future implementation choices.

## Honest scope statement
This is an academic prototype, not a fully autonomous agent. It does not yet have push notifications, calendar integration, Android APK packaging, on-device LLM inference or multi-user authentication.
