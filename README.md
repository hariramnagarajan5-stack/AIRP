---
title: Agentic Incident Response Platform
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.44.1
python_version: "3.11"
app_file: app.py
pinned: false
license: mit
---

# 🤖 Agentic Incident Response Platform

A multi-agent LangGraph + Gradio application that analyzes incident logs using three
parallel "expert" strategies (RAG over your own knowledge base, live web search, and
LLM-only reasoning), lets a human pick the best remediation, then sends it directly to
**Slack** and creates a ticket in **JIRA**.

## How it works

1. Paste incident logs / JSON / screenshots into the **Analysis** tab.
2. Click **Run Analysis** — three experts independently propose a root cause and
   remediation steps, each with a confidence score:
   - 📚 **RAG** — grounded in documents you upload in the **RAG** tab
   - 🌐 **Web** — grounded in a live Tavily web search
   - 🧠 **LLM** — the model's own knowledge
3. Pick the remediation you trust most.
4. Click **🚀 Use Selected → Send to Slack & JIRA** — this immediately posts a
   formatted incident summary to your Slack channel and opens a ticket in your
   JIRA project.

## Required configuration (Space secrets)

This Space needs API keys/tokens to talk to your LLM provider, Slack, and JIRA.
Set these under **Settings → Variables and secrets** on this Space (as *secrets*,
not public variables):

| Secret | Required | Notes |
|---|---|---|
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` or `OPENROUTER_API_KEY` | Yes (one) | LLM provider |
| `SLACK_BOT_TOKEN` | For Slack posting | `xoxb-...`, needs `chat:write` scope |
| `SLACK_CHANNEL` | Optional | Defaults to `#incidents` |
| `JIRA_SERVER` | For JIRA tickets | e.g. `https://your-domain.atlassian.net` |
| `JIRA_USERNAME` | For JIRA tickets | Your Atlassian account email |
| `JIRA_API_TOKEN` | For JIRA tickets | From id.atlassian.com/manage/api-tokens |
| `JIRA_PROJECT_KEY` | Optional | Defaults to `OPS` |
| `TAVILY_API_KEY` | Optional | Enables the Web Search expert |

If any of these are missing, the corresponding feature degrades gracefully and
shows a warning in the UI rather than failing the whole app.

You can also paste keys directly into the **Config** tab at runtime instead of
using secrets — useful for quick testing.

## Files

- `app.py` — main application (LangGraph pipeline + Gradio UI)
- `requirements.txt` — Python dependencies
- `incidents_rag.csv` — example knowledge base you can upload in the **RAG** tab
