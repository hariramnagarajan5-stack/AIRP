# 🎯 Updated: Direct Slack & JIRA Integration

## ✨ What's New

Your app now has **DIRECT integration** with Slack and JIRA!

### Key Features

✅ **Click "Use Selected as Final Remediation"**
  - Slack message sent INSTANTLY to your channel
  - JIRA ticket created INSTANTLY in your project
  - No delays, no Composio dependency

✅ **Real-Time Status**
  - See confirmation: ✅ Slack Message Sent
  - See confirmation: ✅ JIRA Ticket Created
  - Shows issue key, channel, message ID

✅ **Direct SDK Integration**
  - Uses `slack-sdk` (official Slack Python SDK)
  - Uses `jira` (official Jira Python SDK)
  - No REST API abstractions

---

## 📦 Files Updated

### 1. **app.py** (39 KB)
Updated with:
- `send_slack_message()` - Sends messages using Slack SDK
- `create_jira_ticket()` - Creates tickets using Jira SDK
- `finalize()` function - Sends to Slack & creates JIRA when clicked
- Config tab - Enter credentials directly in UI

### 2. **requirements.txt**
Added:
```
slack-sdk>=3.23.0
jira>=3.13.0
```

### 3. **SLACK_JIRA_SETUP.md**
Complete setup guide with:
- How to create Slack bot
- How to get Slack token
- How to create JIRA API token
- Troubleshooting steps

---

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Get Credentials

**Slack Bot Token:**
1. Go to https://api.slack.com/apps
2. Create new app
3. Add scopes: `chat:write`, `channels:read`
4. Install to workspace
5. Copy Bot Token (xoxb-...)

**JIRA Credentials:**
1. Get server URL from your JIRA instance
2. Go to https://id.atlassian.com/manage/api-tokens
3. Create API token
4. Note your username (email)

### Step 3: Run App

**Option A: Environment Variables (Recommended)**
```bash
export SLACK_BOT_TOKEN="xoxb-..."
export SLACK_CHANNEL="#incidents"
export JIRA_SERVER="https://your-domain.atlassian.net"
export JIRA_USERNAME="your-email@company.com"
export JIRA_API_TOKEN="your-token"
export JIRA_PROJECT_KEY="OPS"
export OPENAI_API_KEY="sk-..."

python3 app.py
```

**Option B: Via Web UI**
```bash
python3 app.py
# Go to "Config" tab
# Paste all credentials
```

---

## 📖 How It Works

### Before (Composio)
```
Click "Use Selected..."
    ↓
Composio REST API
    ↓
Timeout / Error / Mock
```

### Now (Direct SDK)
```
Click "🚀 Use Selected → Send to Slack & JIRA"
    ↓
Slack SDK (direct) + Jira SDK (direct)
    ↓
✅ Instant Slack message
✅ Instant JIRA ticket
✅ Confirmation shown in UI
```

---

## 🎯 Usage Workflow

### 1. Paste Incident Logs
```
Go to "Analysis" tab
Paste logs from your logs/JSON/screenshots
```

### 2. Click "Run Analysis"
```
App analyzes with 3 experts:
- RAG (knowledge base)
- Web (Tavily search)
- LLM (your LLM model)

Shows confidence scores for each
```

### 3. Pick Best Remediation
```
Select the option you trust most
(usually the one with highest confidence)
```

### 4. Click "🚀 Use Selected → Send to Slack & JIRA"
```
✅ Slack message appears in #incidents channel
✅ JIRA ticket created in OPS project
✅ Results shown in Final & Status tabs
```

---

## 🔧 Configuration

### In Environment Variables

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-1234567890-...
SLACK_CHANNEL=#incidents

# JIRA
JIRA_SERVER=https://your-domain.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token
JIRA_PROJECT_KEY=OPS

# LLM (pick one)
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...

# Optional
TAVILY_API_KEY=tvly-...
```

### In UI (Config Tab)

```
Slack Bot Token:        [xoxb-...]
Slack Channel:          [#incidents]
JIRA Server:            [https://your-domain.atlassian.net]
JIRA Username:          [your-email@company.com]
JIRA API Token:         [your-token]
JIRA Project Key:       [OPS]
LLM Key:                [sk-...]
Tavily Key (optional):  [tvly-...]
```

---

## ✅ What Gets Sent

### Slack Message (Auto-Formatted)
```
🚨 **P1 Incident** in order-service

*Root Cause:* Database connection pool exhaustion

*First Action:* Identify slow queries using EXPLAIN ANALYZE

*Remediation Steps:*
1. Add indexes on filtered columns
2. Optimize JOIN operations
3. Implement connection timeouts
4. Monitor with APM tools
```

### JIRA Ticket (Auto-Created)
```
Project:     OPS
Type:        Task
Summary:     Connection timed out in order-service
Description: Full remediation cookbook with all steps
Priority:    High (auto-mapped from P1/P2/P3/P4)
```

---

## 🧪 Testing

### Test Slack Connection

```bash
python3 << 'EOF'
from slack_sdk import WebClient

token = "xoxb-your-token"
client = WebClient(token=token)

try:
    response = client.chat_postMessage(
        channel="#test-channel",
        text="Test message"
    )
    print(f"✅ Slack working! Message: {response['ts']}")
except Exception as e:
    print(f"❌ Slack error: {e}")
EOF
```

### Test JIRA Connection

```bash
python3 << 'EOF'
from jira import JIRA

try:
    jira = JIRA(
        server="https://your-domain.atlassian.net",
        basic_auth=("your@email.com", "your-token")
    )
    print(f"✅ JIRA connected! Projects: {jira.projects()}")
except Exception as e:
    print(f"❌ JIRA error: {e}")
EOF
```

---

## 🆘 Common Issues & Fixes

| Issue | Solution |
|-------|----------|
| "Slack Bot Token not configured" | Set `SLACK_BOT_TOKEN` env var or paste in Config tab |
| "Bot not in channel" | Invite bot to #incidents channel in Slack |
| "Channel not found" | Check channel name (should be `#incidents`) |
| "JIRA authentication failed" | Verify JIRA credentials (server, username, token) |
| "Project not found" | Use correct JIRA project key |
| Import errors | Run `pip install -r requirements.txt` |

**See full troubleshooting:** Open `SLACK_JIRA_SETUP.md`

---

## 📋 Setup Checklist

- [ ] Downloaded latest `app.py` and `requirements.txt`
- [ ] Ran `pip install -r requirements.txt`
- [ ] Created Slack app at api.slack.com/apps
- [ ] Added bot scopes: `chat:write`, `channels:read`
- [ ] Installed bot to workspace
- [ ] Invited bot to #incidents channel
- [ ] Copied Slack bot token (xoxb-...)
- [ ] Created JIRA API token at id.atlassian.com/manage/api-tokens
- [ ] Noted JIRA server URL, username, project key
- [ ] Set environment variables OR ready to paste in UI
- [ ] Run `python3 app.py`
- [ ] Open http://localhost:7860
- [ ] Test: Paste logs → Run Analysis → Pick → Send to Slack & JIRA
- [ ] ✅ Slack message appears in channel
- [ ] ✅ JIRA ticket appears in project

---

## 🎓 Architecture

```
┌──────────────────────────┐
│   Incident Analysis      │
│  RAG | Web | LLM Expert  │
└────────────┬─────────────┘
             │
             ↓
   User selects remediation
             │
             ↓
┌─────────────────────────────────────┐
│ Click "Use Selected..."             │
│ (Send to Slack & JIRA)              │
└────┬──────────────────────┬─────────┘
     │                      │
     ↓                      ↓
Slack SDK              Jira SDK
(slack_sdk)            (jira package)
     │                      │
     ↓                      ↓
  Slack                   JIRA
#incidents            OPS-123
  (Message)           (Ticket)
     │                      │
     ↓                      ↓
✅ Sent             ✅ Created
```

---

## 🚀 Start Now

```bash
# 1. Install
pip install -r requirements.txt

# 2. Set credentials (option A)
export SLACK_BOT_TOKEN="xoxb-..."
export JIRA_SERVER="https://..."
export JIRA_USERNAME="you@email.com"
export JIRA_API_TOKEN="..."
export OPENAI_API_KEY="sk-..."

# 3. Run
python3 app.py

# 4. Open browser
# http://localhost:7860
```

---

## 📚 Documentation

- **SLACK_JIRA_SETUP.md** - Detailed setup guide
- **incidents_rag.csv** - 100 incident/resolution examples for RAG
- **QUICK_START.md** - 5-minute quickstart

---

**That's it! You now have direct Slack & JIRA integration.** 🎉

When you click "Use Selected as Final Remediation":
- ✅ Slack message sent to #incidents
- ✅ JIRA ticket created in your project
- ✅ Status shown in app UI

No more Composio issues, no more mocks, just direct real-time integration! 🚀
