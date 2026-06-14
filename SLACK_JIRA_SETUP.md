# Direct Slack & JIRA Integration Setup Guide

## 🎯 What's New

Your app now sends **Slack messages DIRECTLY** when you click "Use Selected as Final Remediation"!

✅ **Slack Message**: Sent instantly to your channel in real-time  
✅ **JIRA Ticket**: Created instantly in your JIRA project  
❌ No more Composio dependency - direct SDK integration

---

## 📋 Prerequisites

### Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `slack-sdk` - Direct Slack API client
- `jira` - Direct JIRA API client
- `slack-sdk>=3.23.0`
- `jira>=3.13.0`

---

## 🔐 Setup Slack Bot Token

### Step 1: Create Slack App

1. Go to: https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. App Name: `Incident Response Bot`
4. Workspace: Select your Slack workspace
5. Click **"Create App"**

### Step 2: Add Bot Permissions

1. In left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Scopes"** section
3. Under **"Bot Token Scopes"**, click **"Add an OAuth Scope"**
4. Add these scopes:
   - `chat:write` (send messages)
   - `channels:read` (read channel info)
   - `users:read` (optional)

### Step 3: Install to Workspace

1. Scroll up to **"OAuth Tokens for Your Workspace"**
2. Click **"Install to Workspace"**
3. Click **"Allow"** on permission screen
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
   ```
   xoxb-1234567890-1234567890-xxxxxxxxxxxxx
   ```

### Step 4: Add Bot to Channel

1. Go to your Slack workspace
2. Go to `#incidents` channel (or your chosen channel)
3. Click channel name → "Details"
4. Click "Add apps"
5. Search for your bot name
6. Click "Add"

---

## 🔐 Setup JIRA Credentials

### Step 1: Get JIRA Server URL

1. Go to your JIRA instance
2. Copy the server URL from address bar:
   ```
   https://your-domain.atlassian.net
   ```

### Step 2: Create JIRA API Token

1. Go to: https://id.atlassian.com/manage/api-tokens
2. Click **"Create API token"**
3. Label: `Incident Bot`
4. Click **"Create"**
5. Copy the token (long random string)

### Step 3: Note Your JIRA Username

Your JIRA username is usually your **email address** registered with Jira.

---

## ⚙️ Configure Environment Variables

### Option 1: Environment Variables (Recommended)

```bash
# Slack
export SLACK_BOT_TOKEN="xoxb-1234567890-1234567890-xxxxxxxxxxxxx"
export SLACK_CHANNEL="#incidents"

# JIRA
export JIRA_SERVER="https://your-domain.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_API_TOKEN="your-api-token-here"
export JIRA_PROJECT_KEY="OPS"

# LLM (pick one)
export OPENAI_API_KEY="sk-..."
# OR
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Option 2: Via Web UI

Run app and paste credentials in "Config" tab:
```
Slack Bot Token: [xoxb-...]
Slack Channel: [#incidents]
JIRA Server: [https://your-domain.atlassian.net]
JIRA Username: [your-email@company.com]
JIRA API Token: [your-token]
JIRA Project Key: [OPS]
```

---

## 🚀 Run the App

```bash
python3 app.py
```

Open: http://localhost:7860

---

## 📖 How to Use

### 1. Paste Incident Logs

Go to **"Analysis"** tab and paste your logs:

```
2026-06-13T09:00:01.100Z WARN order-service connection_pool active=48 max=50
2026-06-13T09:00:02.200Z ERROR order-service HikariPool-1 - Connection timed out
```

### 2. Click "Run Analysis"

The app will:
- ✅ Parse the incident
- ✅ Get RAG remediation (from uploaded knowledge base)
- ✅ Get Web remediation (from Tavily search)
- ✅ Get LLM remediation (from your LLM)

### 3. Review the 3 Options

See side-by-side:
- 📚 **RAG Retrieval** - From your knowledge base
- 🌐 **Web Search** - From the internet
- 🧠 **LLM Knowledge** - From model's knowledge

Confidence scores show which expert is most confident.

### 4. Pick the Best One

Select the remediation option you trust most.

### 5. Click "🚀 Use Selected → Send to Slack & JIRA"

**Instantly:**
- ✅ Slack message sent to your channel
- ✅ JIRA ticket created in your project
- ✅ Final remediation displayed

---

## 🎯 What Gets Sent

### To Slack

```
🚨 **P1 Incident** in order-service

*Root Cause:* High database query latency causing connection pool exhaustion

*First Action:* Identify slow queries using database logs and EXPLAIN ANALYZE

*Remediation Steps:*
1. Add missing indexes on frequently filtered columns
2. Optimize JOIN operations
3. Implement connection timeout policies
4. Monitor with APM tools
```

### To JIRA

```
Project:     OPS
Type:        Task
Summary:     Connection timed out in order-service
Description: Full remediation cookbook with all steps
Priority:    High (auto-mapped from incident severity)
```

---

## 🧪 Testing

### Test 1: Verify Slack Connection

```python
from slack_sdk import WebClient

token = "xoxb-your-token"
client = WebClient(token=token)

response = client.chat_postMessage(
    channel="#test-channel",
    text="Test message from Python"
)
print(f"Message sent: {response['ts']}")
```

### Test 2: Verify JIRA Connection

```python
from jira import JIRA

jira = JIRA(
    server="https://your-domain.atlassian.net",
    basic_auth=("your-email@company.com", "your-api-token")
)

issue = jira.create_issue(
    project="OPS",
    summary="Test Issue",
    description="Testing JIRA connection",
    issuetype="Task",
    priority="Medium"
)
print(f"Issue created: {issue.key}")
```

---

## 🆘 Troubleshooting

### Problem: "Slack Bot Token not configured"

**Error in UI:**
```
⚠️ Slack: Slack Bot Token not configured. Set SLACK_BOT_TOKEN env var.
```

**Solution:**
1. Get bot token from https://api.slack.com/apps → OAuth & Permissions
2. Set env var: `export SLACK_BOT_TOKEN="xoxb-..."`
3. OR paste in "Config" tab → Slack Bot Token field

### Problem: "Bot not in channel"

**Error:**
```
❌ Slack Error: Slack API Error: not_in_channel
```

**Solution:**
1. Go to Slack channel (e.g., #incidents)
2. Click channel name → "Details"
3. Click "Add apps"
4. Search for your bot
5. Click "Add"

### Problem: "Channel not found"

**Error:**
```
❌ Slack Error: Slack API Error: channel_not_found
```

**Solution:**
1. Check channel name is correct (e.g., `#incidents`)
2. Make sure bot is invited to that channel
3. Use exact channel name from Slack

### Problem: "JIRA Error: Project not found"

**Error:**
```
❌ JIRA Error: Project with key 'OPS' not found
```

**Solution:**
1. Go to your JIRA instance
2. Check correct project key (from URL or project settings)
3. Set `export JIRA_PROJECT_KEY="YOUR_KEY"`

### Problem: "JIRA Error: Authentication failed"

**Error:**
```
❌ JIRA Error: authentication failed
```

**Solution:**
1. Verify JIRA server URL: `https://your-domain.atlassian.net`
2. Verify username: usually your email
3. Verify API token is correct (create new one if needed)
4. Check token hasn't expired

---

## 🔄 Workflow Example

```
1. Paste logs:
   "2026-06-13T09:00:01.100Z WARN order-service connection_pool..."

2. Click "Run Analysis"
   ↓
   App analyzes incident with 3 experts:
   - RAG: 85% confidence (matched knowledge base)
   - Web: 70% confidence (found similar issue)
   - LLM: 60% confidence (general knowledge)

3. Radio automatically selects: "RAG Retrieval" (highest confidence)

4. Click "🚀 Use Selected → Send to Slack & JIRA"
   ↓
   ✅ Slack message sent to #incidents
   ✅ JIRA ticket created: OPS-123
   ✅ Final remediation displayed

5. Result:
   Final Remediation Tab: Shows full remediation steps
   Status Tab: Shows "✅ Slack: Sent" and "✅ JIRA: Created: OPS-123"
```

---

## 📊 Architecture

```
┌─────────────────────────────┐
│   Incident Analysis         │
│  (RAG + Web + LLM experts)  │
└────────────┬────────────────┘
             │
             ↓
    User selects best option
             │
             ↓
┌──────────────────────────────────┐
│  "Use Selected as Final..."      │
│  (Click button)                  │
└────┬──────────────────────────┬──┘
     │                          │
     ↓                          ↓
  Slack SDK              Jira SDK
  (Direct)               (Direct)
     │                          │
     ↓                          ↓
Slack Channel          JIRA Project
#incidents             OPS-123
```

---

## 🎓 Environment Variables Summary

| Variable | Example | Required | Source |
|----------|---------|----------|--------|
| `SLACK_BOT_TOKEN` | `xoxb-...` | Yes | api.slack.com/apps → OAuth & Permissions |
| `SLACK_CHANNEL` | `#incidents` | No (default: #incidents) | Your Slack workspace |
| `JIRA_SERVER` | `https://your-domain.atlassian.net` | Yes | Your JIRA URL |
| `JIRA_USERNAME` | `your@email.com` | Yes | Your JIRA account email |
| `JIRA_API_TOKEN` | `long-token-string` | Yes | id.atlassian.com/manage/api-tokens |
| `JIRA_PROJECT_KEY` | `OPS` | No (default: OPS) | Your JIRA project |
| `OPENAI_API_KEY` | `sk-...` | Yes (pick one LLM) | openai.com |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Yes (pick one LLM) | console.anthropic.com |
| `TAVILY_API_KEY` | `tvly-...` | No (optional) | tavily.com |

---

## 🚀 Quick Start (3 Steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set environment variables
export SLACK_BOT_TOKEN="xoxb-..."
export JIRA_SERVER="https://your-domain.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_API_TOKEN="your-token"
export OPENAI_API_KEY="sk-..."

# 3. Run app
python3 app.py
# Open http://localhost:7860
```

---

## ✅ Verification Checklist

- [ ] Slack app created at api.slack.com/apps
- [ ] Bot scopes added: `chat:write`, `channels:read`
- [ ] Bot installed to workspace
- [ ] Bot invited to #incidents channel
- [ ] Bot token copied: `xoxb-...`
- [ ] JIRA API token created: id.atlassian.com/manage/api-tokens
- [ ] JIRA server URL verified: `https://your-domain.atlassian.net`
- [ ] Environment variables set or ready to paste in UI
- [ ] `pip install -r requirements.txt` run successfully
- [ ] App launches: `python3 app.py`
- [ ] Can paste logs and run analysis
- [ ] Can select remediation option
- [ ] Can click "Use Selected..." button
- [ ] ✅ Slack message appears in channel
- [ ] ✅ JIRA ticket appears in project

---

**Ready? Start with:** `python3 app.py` 🚀
