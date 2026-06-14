"""
Agentic Incident Response Platform - Direct Slack Integration
Single-file LangGraph multi-agent pipeline + Gradio UI.

Pipeline:
  1. Parser agent extracts structured incident details from the raw input.
  2. Three independent "expert" agents each propose a remediation:
       - RAG expert   (grounded in user-uploaded knowledge-base docs)
       - Web expert   (grounded in a real Tavily web search)
       - LLM expert   (model's own knowledge only)
     Each reports its own confidence score (0 if not used / no response).
  3. Human-in-the-loop: the user reviews all three side-by-side and picks
     one as the final remediation.
  4. When "Use Selected as Final Remediation" is clicked:
     - Cookbook is generated
     - JIRA ticket is created (optional)
     - Slack message is sent DIRECTLY to your channel in real-time ✅
"""

import os, json, base64
from pathlib import Path
from typing import TypedDict, Optional
import gradio as gr
from langgraph.graph import StateGraph, END

# ---------------- Workaround for gradio_client schema bug ----------------
# Some gradio/gradio_client versions crash with
# "TypeError: argument of type 'bool' is not iterable" when generating API
# schema info, because JSON Schema allows a bare `true`/`false` as a complete
# schema (e.g. for `additionalProperties: true` on gr.State's "any" type), but
# gradio_client's schema-to-python-type converter assumes every schema is a
# dict. This crashes the "/" route's API-info generation, which in turn makes
# demo.launch()'s own startup health-check fail and raise a misleading
# "localhost not accessible, set share=True" error.
#
# Fix: wrap the offending converter so boolean schemas are treated as "Any"
# instead of raising. This is purely additive and safe to no-op if the
# installed gradio_client doesn't have this function under this name.
try:
    import gradio_client.utils as _gc_utils

    _orig_json_schema_to_python_type = _gc_utils._json_schema_to_python_type

    def _safe_json_schema_to_python_type(schema, defs=None):
        if isinstance(schema, bool):
            return "Any"
        return _orig_json_schema_to_python_type(schema, defs)

    _gc_utils._json_schema_to_python_type = _safe_json_schema_to_python_type
except Exception:
    pass
# ---------------------------------------------------------------------------

# ---------------- Workaround for Starlette TemplateResponse shim removal ---
# gradio 4.44.1's routes.py calls the OLD Starlette signature:
#     templates.TemplateResponse(name: str, context: dict, ...)
# Newer Starlette releases removed the back-compat shim and require:
#     templates.TemplateResponse(request, name: str, context: dict, ...)
# With the old call on a new Starlette, "name" (a string) lands in the
# `request` slot and `context` (a dict) lands in the `name` slot. Jinja2 then
# tries to use that dict as part of its template-cache key, raising
# "TypeError: unhashable type: 'dict'". This 500s "/", which in turn makes
# demo.launch()'s startup health-check fail with a misleading
# "set share=True" error.
#
# Fix: if the installed Starlette has the new (request, name, context)
# signature, wrap TemplateResponse so old-style (name, context) calls are
# transparently rewritten to the new form (pulling `request` out of the
# context dict, as gradio always includes it). No-ops on old Starlette where
# the shim is still present.
try:
    import inspect
    from starlette.templating import Jinja2Templates

    _orig_template_response = Jinja2Templates.TemplateResponse
    _trp_params = list(inspect.signature(_orig_template_response).parameters)

    if len(_trp_params) >= 2 and _trp_params[1] == "request":
        def _compat_template_response(self, *args, **kwargs):
            if args and isinstance(args[0], str):
                name = args[0]
                context = args[1] if len(args) > 1 else kwargs.pop("context", {})
                rest = args[2:]
                request = (context or {}).get("request")
                if request is not None:
                    return _orig_template_response(self, request, name, context, *rest, **kwargs)
            return _orig_template_response(self, *args, **kwargs)

        Jinja2Templates.TemplateResponse = _compat_template_response
except Exception:
    pass
# ---------------------------------------------------------------------------

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from anthropic import Anthropic
except Exception:
    Anthropic = None

try:
    import requests
except Exception:
    requests = None

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except Exception:
    WebClient = None
    SlackApiError = None

try:
    from jira import JIRA
except Exception:
    JIRA = None

# ---------------- Config / Env Vars ----------------
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

# Direct Slack & JIRA Integration
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#incidents")

JIRA_SERVER = os.environ.get("JIRA_SERVER")
JIRA_USERNAME = os.environ.get("JIRA_USERNAME")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "OPS")

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
RAG_CORPUS_CHAR_LIMIT = 8000


# ============ SLACK INTEGRATION ============
def send_slack_message(message_text: str, channel: Optional[str] = None, bot_token: Optional[str] = None) -> tuple:
    """Send message directly to Slack using Slack SDK.
    
    Returns: (success: bool, message_ts: str, error: str)
    """
    token = (bot_token or SLACK_BOT_TOKEN or "").strip()
    target_channel = (channel or SLACK_CHANNEL or "#incidents").strip()
    
    if not token:
        return False, "", "Slack Bot Token not configured. Set SLACK_BOT_TOKEN env var."
    
    if WebClient is None:
        return False, "", "Slack SDK not installed. Run: pip install slack-sdk"
    
    try:
        client = WebClient(token=token)
        
        # Send message
        response = client.chat_postMessage(
            channel=target_channel,
            text=message_text,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text
                    }
                }
            ]
        )
        
        message_ts = response.get("ts", "")
        return True, message_ts, None
        
    except SlackApiError as e:
        error_msg = f"Slack API Error: {e.response['error']}"
        if "channel_not_found" in str(e):
            error_msg += f"\n   Channel '{target_channel}' not found. Create it or use different channel."
        elif "not_in_channel" in str(e):
            error_msg += f"\n   Bot not in channel '{target_channel}'. Invite the bot to the channel."
        elif "invalid_auth" in str(e):
            error_msg += f"\n   Invalid Slack bot token. Check SLACK_BOT_TOKEN."
        return False, "", error_msg
    except Exception as e:
        return False, "", f"Error sending Slack message: {str(e)}"


# ============ JIRA INTEGRATION ============
def create_jira_ticket(
    summary: str,
    description: str,
    priority: str = "Medium",
    issue_type: str = "Task",
    project_key: Optional[str] = None,
    jira_server: Optional[str] = None,
    jira_user: Optional[str] = None,
    jira_token: Optional[str] = None,
) -> tuple:
    """Create JIRA ticket using Jira SDK.
    
    Returns: (success: bool, issue_key: str, error: str)
    """
    server = (jira_server or JIRA_SERVER or "").strip()
    username = (jira_user or JIRA_USERNAME or "").strip()
    token = (jira_token or JIRA_API_TOKEN or "").strip()
    proj = (project_key or JIRA_PROJECT_KEY or "OPS").strip()
    
    if not server or not username or not token:
        return False, "", "JIRA credentials not configured. Set JIRA_SERVER, JIRA_USERNAME, JIRA_API_TOKEN env vars."
    
    if JIRA is None:
        return False, "", "Jira SDK not installed. Run: pip install jira"
    
    try:
        jira = JIRA(
            server=server,
            basic_auth=(username, token),
            options={"verify": True}
        )
        
        # Map priority
        priority_map = {
            "P1": "Highest", "P2": "High", "P3": "Medium", "P4": "Low",
            "Highest": "Highest", "High": "High", "Medium": "Medium", "Low": "Low",
            "Critical": "Highest"
        }
        jira_priority = priority_map.get(priority, "Medium")
        
        issue_dict = {
            "project": {"key": proj},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
            "priority": {"name": jira_priority},
        }
        
        issue = jira.create_issue(fields=issue_dict)
        return True, issue.key, None
        
    except Exception as e:
        error_msg = str(e)
        if "project" in error_msg.lower():
            error_msg += f"\n   Project key '{proj}' might not exist."
        if "authentication" in error_msg.lower():
            error_msg += f"\n   Check JIRA credentials."
        return False, "", f"JIRA Error: {error_msg}"


# ============ LLM & UTILITIES ============
def resolve_client(api_key: Optional[str] = None):
    """Resolve LLM client from API key."""
    key = (api_key or "").strip()

    if key:
        if key.startswith("sk-ant-"):
            if Anthropic is None:
                return None, None, None
            return Anthropic(api_key=key), ANTHROPIC_MODEL, "anthropic"
        if key.startswith("sk-or-"):
            if OpenAI is None:
                return None, None, None
            return OpenAI(api_key=key, base_url=OPENROUTER_BASE_URL), OPENROUTER_MODEL, "openai"
        if OpenAI is not None:
            return OpenAI(api_key=key), MODEL, "openai"
        if Anthropic is not None:
            return Anthropic(api_key=key), ANTHROPIC_MODEL, "anthropic"
        return None, None, None

    if OPENROUTER_API_KEY and OpenAI is not None:
        return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL), OPENROUTER_MODEL, "openai"
    if OPENAI_API_KEY and OpenAI is not None:
        return OpenAI(api_key=OPENAI_API_KEY), MODEL, "openai"
    if ANTHROPIC_API_KEY and Anthropic is not None:
        return Anthropic(api_key=ANTHROPIC_API_KEY), ANTHROPIC_MODEL, "anthropic"
    return None, None, None


def llm(prompt: str, image_b64: Optional[str] = None, api_key: Optional[str] = None) -> str:
    """Call LLM."""
    client_local, model_name, provider = resolve_client(api_key)

    if client_local is None:
        return json.dumps({
            "error": "No usable LLM API key found. Add a key in the 'API Key Setup' tab."
        })

    try:
        if provider == "openai":
            content = [{"type": "text", "text": prompt}]
            if image_b64:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                })
            resp = client_local.chat.completions.create(
                model=model_name,
                max_tokens=1024,
                messages=[{"role": "user", "content": content}],
            )
            text = resp.choices[0].message.content
            return text if isinstance(text, str) else str(text)

        content = []
        if image_b64:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
            })
        content.append({"type": "text", "text": prompt})
        resp = client_local.messages.create(
            model=model_name,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        return resp.content[0].text
    except Exception as e:
        return json.dumps({"error": f"LLM call failed: {e}"})


def safe_json(text: str, fallback: dict) -> dict:
    """Parse JSON from LLM response."""
    try:
        s = text.find("{")
        e = text.rfind("}") + 1
        data = json.loads(text[s:e])
    except Exception:
        return {**fallback, "_error": f"Could not parse JSON: {text[:100]!r}"}

    if isinstance(data, dict) and set(data.keys()) == {"error"}:
        return {**fallback, "_error": data["error"]}
    return data


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1")
    return bool(value)


def read_text_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def web_search(query: str, api_key: Optional[str] = None, max_results: int = 3):
    """Tavily web search."""
    key = (api_key or TAVILY_API_KEY or "").strip()
    if not key or requests is None:
        return [], None

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": max_results, "search_depth": "basic"},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [
            {
                "title": r.get("title", "") or "",
                "url": r.get("url", "") or "",
                "content": (r.get("content") or "")[:400],
            }
            for r in data.get("results", [])
        ]
        return results, None
    except Exception as e:
        return [], f"Web search failed: {e}"


# ============ STATE & AGENTS ============
class IncidentState(TypedDict):
    raw_input: str
    image_b64: Optional[str]
    llm_api_key: str
    tavily_api_key: str
    slack_bot_token: str
    slack_channel: str
    jira_server: str
    jira_username: str
    jira_api_token: str
    jira_project: str
    rag_corpus: str
    consolidated: dict
    severity: dict
    rag_result: Optional[dict]
    rag_confidence: int
    web_result: Optional[dict]
    web_confidence: int
    web_results: list
    llm_result: Optional[dict]
    llm_confidence: int
    human_decision: str
    remediation: dict
    cookbook: str
    errors: list


def parser_agent(state: IncidentState) -> dict:
    """Parse incident."""
    prompt = f"""Analyze this incident and return ONLY JSON:
{{
  "timestamp": "...",
  "service": "...",
  "error": "...",
  "category": "Database|Network|Infrastructure|Kubernetes",
  "severity": "P1|P2|P3|P4",
  "impact": "Low|Medium|High|Critical"
}}
INPUT:
{state['raw_input']}
"""
    fallback = {
        "timestamp": "unknown", "service": "unknown", "error": "unparsed",
        "category": "Infrastructure", "severity": "P3", "impact": "Medium"
    }
    out = safe_json(llm(prompt, state.get("image_b64"), state.get("llm_api_key")), fallback)
    errors = list(state.get("errors", []))
    if "_error" in out:
        errors.append(f"Parser: {out.pop('_error')}")

    return {
        "consolidated": out,
        "severity": {"severity": out.get("severity", "P3"), "impact": out.get("impact", "Medium")},
        "errors": errors,
    }


def rag_agent(state: IncidentState) -> dict:
    """RAG expert."""
    errors = list(state.get("errors", []))
    corpus = (state.get("rag_corpus") or "").strip()
    if not corpus:
        return {"rag_result": None, "rag_confidence": 0, "errors": errors}

    c = state["consolidated"]
    prompt = f"""Using ONLY the knowledge base, suggest remediation. Return ONLY JSON:
{{
  "relevant": true|false,
  "root_cause": "...",
  "remediation": ["step1", "step2"],
  "confidence": 0-100
}}
INCIDENT: {json.dumps(c)}
KNOWLEDGE BASE:
{corpus[:RAG_CORPUS_CHAR_LIMIT]}
"""
    out = safe_json(llm(prompt, None, state.get("llm_api_key")), {
        "relevant": False, "root_cause": "", "remediation": [], "confidence": 0
    })
    if "_error" in out:
        errors.append(f"RAG: {out.pop('_error')}")
        return {"rag_result": None, "rag_confidence": 0, "errors": errors}

    if not _to_bool(out.get("relevant")) or not out.get("root_cause"):
        return {"rag_result": None, "rag_confidence": 0, "errors": errors}

    return {
        "rag_result": {"root_cause": out.get("root_cause"), "remediation": out.get("remediation") or []},
        "rag_confidence": _to_int(out.get("confidence"), 0),
        "errors": errors,
    }


def web_agent(state: IncidentState) -> dict:
    """Web search expert."""
    errors = list(state.get("errors", []))
    c = state["consolidated"]
    query = " ".join(str(c.get(k) or "") for k in ("service", "error", "category")).strip() or "incident"
    search_results, search_err = web_search(query, state.get("tavily_api_key"))
    if search_err:
        errors.append(search_err)

    if not search_results:
        return {"web_result": None, "web_confidence": 0, "web_results": [], "errors": errors}

    web_context = "\n".join(f"- {r['title']} ({r['url']}): {r['content']}" for r in search_results)
    prompt = f"""Using ONLY web results, suggest remediation. Return ONLY JSON:
{{
  "root_cause": "...",
  "remediation": ["step1", "step2"],
  "confidence": 0-100
}}
INCIDENT: {json.dumps(c)}
WEB RESULTS:
{web_context}
"""
    out = safe_json(llm(prompt, None, state.get("llm_api_key")), {"root_cause": "", "remediation": [], "confidence": 0})
    if "_error" in out:
        errors.append(f"Web: {out.pop('_error')}")
        return {"web_result": None, "web_confidence": 0, "web_results": search_results, "errors": errors}

    if not out.get("root_cause"):
        return {"web_result": None, "web_confidence": 0, "web_results": search_results, "errors": errors}

    return {
        "web_result": {"root_cause": out.get("root_cause"), "remediation": out.get("remediation") or []},
        "web_confidence": _to_int(out.get("confidence"), 0),
        "web_results": search_results,
        "errors": errors,
    }


def llm_agent(state: IncidentState) -> dict:
    """LLM expert."""
    errors = list(state.get("errors", []))
    c = state["consolidated"]
    prompt = f"""Act as SRE expert. Suggest root cause and remediation. Return ONLY JSON:
{{
  "root_cause": "...",
  "remediation": ["step1", "step2", "step3"],
  "confidence": 0-100
}}
INCIDENT: {json.dumps(c)}
"""
    out = safe_json(llm(prompt, None, state.get("llm_api_key")), {
        "root_cause": "Unknown", "remediation": ["Investigate manually"], "confidence": 30
    })
    if "_error" in out:
        errors.append(f"LLM: {out.pop('_error')}")
        return {"llm_result": None, "llm_confidence": 0, "errors": errors}

    return {
        "llm_result": {"root_cause": out.get("root_cause", "Unknown"), "remediation": out.get("remediation") or ["Investigate manually"]},
        "llm_confidence": _to_int(out.get("confidence"), 30),
        "errors": errors,
    }


def select_remediation_agent(state: IncidentState) -> dict:
    """Select chosen remediation."""
    choice = state.get("human_decision", "llm")
    rem = state.get(f"{choice}_result")
    if not rem:
        rem = {"root_cause": "No remediation available.", "remediation": []}
    return {"remediation": rem}


def cookbook_agent(state: IncidentState) -> dict:
    """Generate cookbook."""
    rem = state["remediation"]
    steps = "\n".join(f"{i+1}. {s}" for i, s in enumerate(rem.get("remediation", [])))
    cookbook = f"# Incident Response Checklist\n\nRoot Cause: {rem.get('root_cause')}\n\n{steps}\n\n{len(rem.get('remediation', []))+1}. Monitor for 15 minutes."
    return {"cookbook": cookbook}


# ============ GRAPHS ============
analysis_builder = StateGraph(IncidentState)
analysis_builder.add_node("parser", parser_agent)
analysis_builder.add_node("rag", rag_agent)
analysis_builder.add_node("web", web_agent)
analysis_builder.add_node("llm_expert", llm_agent)
analysis_builder.set_entry_point("parser")
analysis_builder.add_edge("parser", "rag")
analysis_builder.add_edge("rag", "web")
analysis_builder.add_edge("web", "llm_expert")
analysis_builder.add_edge("llm_expert", END)
analysis_graph = analysis_builder.compile()

final_builder = StateGraph(IncidentState)
final_builder.add_node("select", select_remediation_agent)
final_builder.add_node("cookbook", cookbook_agent)
final_builder.set_entry_point("select")
final_builder.add_edge("select", "cookbook")
final_builder.add_edge("cookbook", END)
final_graph = final_builder.compile()


# ============ UI FUNCTIONS ============
def generate_rag_data(files):
    if not files:
        return "No files uploaded yet."
    items = []
    for file_path in files:
        text = read_text_file(file_path)
        preview = text[:180].replace("\n", " ")
        items.append(f"- {Path(file_path).name}: {len(text.split())} words | Preview: {preview}")
    return "\n".join(items)


def _extract_attachments(chat_input):
    if isinstance(chat_input, dict):
        text = chat_input.get("text") or ""
        files = chat_input.get("files") or []
    else:
        text, files = (chat_input or ""), []

    image_b64 = None
    extra_texts = []
    for f in files:
        path = f.get("path") if isinstance(f, dict) else f
        if not path:
            continue
        ext = Path(path).suffix.lower()
        if ext in IMAGE_EXTS:
            if image_b64 is None:
                try:
                    with open(path, "rb") as fh:
                        image_b64 = base64.b64encode(fh.read()).decode()
                except Exception:
                    pass
        else:
            content = read_text_file(path)
            if content:
                extra_texts.append(f"--- {Path(path).name} ---\n{content}")

    return text, image_b64, extra_texts


def _format_remediation(result: Optional[dict]) -> str:
    if not result:
        return ""
    lines = []
    if result.get("root_cause"):
        lines.append(f"Root Cause: {result['root_cause']}")
    steps = result.get("remediation") or []
    if steps:
        if lines:
            lines.append("")
        lines.append("Remediation Steps:")
        lines.extend(f"{i+1}. {s}" for i, s in enumerate(steps))
    return "\n".join(lines)


def _format_sources(sources: Optional[list]) -> str:
    if not sources:
        return ""
    lines = ["**Sources:**"]
    for s in sources:
        title = (s.get("title") or s.get("url") or "source").strip()
        url = (s.get("url") or "").strip()
        if url:
            lines.append(f"- [{title}]({url})")
        else:
            lines.append(f"- {title}")
    return "\n".join(lines)


def run_analysis(chat_input, llm_api_key, tavily_api_key, rag_files):
    text, image_b64, extra_texts = _extract_attachments(chat_input)
    combined_text = "\n\n".join([t for t in [text, *extra_texts] if t]).strip()

    rag_corpus = ""
    if rag_files:
        chunks = []
        for fp in rag_files:
            content = read_text_file(fp)
            if content:
                chunks.append(f"--- {Path(fp).name} ---\n{content}")
        rag_corpus = "\n\n".join(chunks)[:RAG_CORPUS_CHAR_LIMIT]

    try:
        result = analysis_graph.invoke({
            "raw_input": combined_text or "",
            "image_b64": image_b64,
            "llm_api_key": (llm_api_key or "").strip(),
            "tavily_api_key": (tavily_api_key or "").strip(),
            "slack_bot_token": "",
            "slack_channel": SLACK_CHANNEL,
            "jira_server": JIRA_SERVER,
            "jira_username": JIRA_USERNAME,
            "jira_api_token": JIRA_API_TOKEN,
            "jira_project": JIRA_PROJECT_KEY,
            "rag_corpus": rag_corpus,
            "errors": [],
        })
    except Exception as e:
        return f"## ❌ Error\n```\n{e}\n```", "", 0, "", "", 0, "", 0, gr.update(), None

    consolidated_md = f"## Consolidated Incident\n```json\n{json.dumps(result['consolidated'], indent=2)}\n```"
    if result.get("errors"):
        consolidated_md += "\n\n## ⚠️ Warnings\n" + "\n".join(f"- {e}" for e in result["errors"])

    rag_text = _format_remediation(result.get("rag_result"))
    rag_conf = _to_int(result.get("rag_confidence"), 0)

    web_text = _format_remediation(result.get("web_result"))
    web_conf = _to_int(result.get("web_confidence"), 0)
    web_sources_md = _format_sources(result.get("web_results"))

    llm_text = _format_remediation(result.get("llm_result"))
    llm_conf = _to_int(result.get("llm_confidence"), 0)

    confidences = {"RAG Retrieval": rag_conf, "Web Search": web_conf, "LLM Knowledge": llm_conf}
    best_choice = max(confidences, key=confidences.get)

    return (
        consolidated_md,
        rag_text, rag_conf,
        web_text, web_sources_md, web_conf,
        llm_text, llm_conf,
        gr.update(value=best_choice),
        result,
    )


def finalize(selection, analysis_state, slack_bot_token, slack_channel, jira_server, jira_user, jira_token, jira_project):
    """Finalize: generate cookbook, send to Slack, create JIRA ticket."""
    if not analysis_state:
        return "_Run analysis first._", ""

    choice_map = {"RAG Retrieval": "rag", "Web Search": "web", "LLM Knowledge": "llm"}
    choice = choice_map.get(selection, "llm")

    state = dict(analysis_state)
    state["human_decision"] = choice
    
    try:
        state = final_graph.invoke(state)
    except Exception as e:
        return f"## ❌ Error\n```\n{e}\n```", ""

    rem = state["remediation"]
    c = state.get("consolidated", {})
    sev = state.get("severity", {})
    cookbook = state["cookbook"]

    # Build final markdown
    final_md = f"## Final Remediation - {selection}\n\n"
    if rem.get("root_cause"):
        final_md += f"**Root Cause:** {rem['root_cause']}\n\n"
    steps = rem.get("remediation") or []
    if steps:
        final_md += "**Steps:**\n" + "\n".join(f"- {s}" for s in steps) + "\n\n"
    final_md += f"## Cookbook\n```\n{cookbook}\n```"

    # Send to Slack
    slack_token = (slack_bot_token or SLACK_BOT_TOKEN or "").strip()
    target_channel = (slack_channel or SLACK_CHANNEL or "#incidents").strip()
    
    slack_msg = (f"🚨 **{sev.get('severity', 'P3')} Incident** in {c.get('service', 'unknown')}\n\n"
                 f"*Root Cause:* {rem.get('root_cause', 'Unknown')}\n\n"
                 f"*First Action:* {(steps[0] if steps else 'Investigate')}\n\n"
                 f"*Remediation Steps:*\n" +
                 "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps)))
    
    slack_success = False
    slack_ts = ""
    slack_error = ""
    
    if slack_token and WebClient:
        success, ts, error = send_slack_message(slack_msg, target_channel, slack_token)
        slack_success = success
        slack_ts = ts
        slack_error = error
        
        if success:
            final_md += f"\n\n✅ **Slack Message Sent**\n- Channel: {target_channel}\n- Message ID: {ts}"
        else:
            final_md += f"\n\n❌ **Slack Error**: {error}"
    else:
        slack_error = "Slack Bot Token not configured. Set SLACK_BOT_TOKEN env var."
        final_md += f"\n\n⚠️  **Slack**: {slack_error}"

    # Create JIRA ticket
    jira_success = False
    jira_key = ""
    jira_error = ""
    
    if jira_server and jira_user and jira_token and JIRA:
        success, key, error = create_jira_ticket(
            summary=f"{c.get('error', 'Incident')} in {c.get('service', 'unknown')}",
            description=cookbook,
            priority=sev.get("severity", "Medium"),
            issue_type="Task",
            project_key=jira_project or JIRA_PROJECT_KEY,
            jira_server=jira_server,
            jira_user=jira_user,
            jira_token=jira_token,
        )
        jira_success = success
        jira_key = key
        jira_error = error
        
        if success:
            final_md += f"\n\n✅ **JIRA Ticket Created**\n- Issue: {key}\n- Project: {jira_project or JIRA_PROJECT_KEY}"
        else:
            final_md += f"\n\n❌ **JIRA Error**: {error}"
    else:
        jira_error = "JIRA not configured. Set JIRA_SERVER, JIRA_USERNAME, JIRA_API_TOKEN env vars."
        final_md += f"\n\n⚠️  **JIRA**: {jira_error}"

    # Summary
    summary = f"**Slack:** {'✅ Sent' if slack_success else f'❌ {slack_error}'}\n"
    summary += f"**JIRA:** {'✅ Created: ' + jira_key if jira_success else f'❌ {jira_error}'}"

    return final_md, summary


# ============ GRADIO UI ============
with gr.Blocks(title="Incident Response Platform") as demo:
    gr.Markdown("""
# 🤖 Agentic Incident Response Platform

**Direct Slack & JIRA Integration** - Messages sent instantly when you click "Use Selected as Final Remediation" ✅

Upload logs → Run Analysis → Pick remediation → Send to Slack & JIRA in one click!
    """)

    with gr.Tabs():
        with gr.TabItem("Analysis"):
            with gr.Row():
                with gr.Column():
                    chat_input = gr.MultimodalTextbox(
                        label="Incident Logs",
                        placeholder="Paste logs...",
                        file_types=[".txt", ".json", ".log", ".md", ".csv", ".png", ".jpg"],
                        file_count="multiple",
                        lines=8,
                    )
                    run_btn = gr.Button("Run Analysis", variant="primary")
                with gr.Column():
                    consolidated = gr.Markdown(label="Incident Summary")

            gr.Markdown("## Remediation Experts")
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### 📚 RAG")
                    rag_conf = gr.Number(label="Confidence", value=0, interactive=False)
                    rag_out = gr.Textbox(label="Result", lines=6, interactive=False)
                with gr.Column():
                    gr.Markdown("### 🌐 Web")
                    web_conf = gr.Number(label="Confidence", value=0, interactive=False)
                    web_out = gr.Textbox(label="Result", lines=6, interactive=False)
                    web_sources = gr.Markdown(label="Sources")
                with gr.Column():
                    gr.Markdown("### 🧠 LLM")
                    llm_conf = gr.Number(label="Confidence", value=0, interactive=False)
                    llm_out = gr.Textbox(label="Result", lines=6, interactive=False)

            selection = gr.Radio(
                choices=["RAG Retrieval", "Web Search", "LLM Knowledge"],
                value="LLM Knowledge",
                label="Pick Remediation"
            )
            finalize_btn = gr.Button("🚀 Use Selected → Send to Slack & JIRA", variant="primary", scale=2)
            
            with gr.Tabs():
                with gr.TabItem("Final"):
                    final_out = gr.Markdown()
                with gr.TabItem("Status"):
                    status_out = gr.Markdown()

            analysis_state = gr.State(None)

        with gr.TabItem("RAG"):
            rag_files = gr.File(label="Upload Knowledge Base", file_count="multiple")
            rag_btn = gr.Button("Generate RAG Data")
            rag_status = gr.Markdown()

        with gr.TabItem("Config"):
            gr.Markdown("""
## LLM API Keys
            """)
            llm_key = gr.Textbox(label="LLM Key (sk-...)", type="password")
            tavily_key = gr.Textbox(label="Tavily Key (tvly-...)", type="password")

            gr.Markdown("## Slack Direct Integration")
            gr.Markdown("Get your Slack Bot Token:")
            gr.Markdown("""
1. Go to https://api.slack.com/apps
2. Create New App or select existing
3. OAuth & Permissions → Bot Token Scopes
4. Add: `chat:write` and `channels:read`
5. Install/Reinstall to Workspace
6. Copy Bot Token (xoxb-...)
            """)
            slack_token = gr.Textbox(label="Slack Bot Token (xoxb-...)", type="password")
            slack_ch = gr.Textbox(label="Slack Channel", value="#incidents")

            gr.Markdown("## JIRA Direct Integration")
            gr.Markdown("Get JIRA credentials:")
            gr.Markdown("""
1. Go to your JIRA instance
2. User → Account Settings → Security
3. Create API Token
4. Note: server URL, username (email), API token
            """)
            jira_srv = gr.Textbox(label="JIRA Server (https://your-domain.atlassian.net)")
            jira_usr = gr.Textbox(label="JIRA Username (email)")
            jira_tok = gr.Textbox(label="JIRA API Token", type="password")
            jira_proj = gr.Textbox(label="JIRA Project Key", value="OPS")

    run_btn.click(
        run_analysis,
        inputs=[chat_input, llm_key, tavily_key, rag_files],
        outputs=[consolidated, rag_out, rag_conf, web_out, web_sources, web_conf, llm_out, llm_conf, selection, analysis_state],
    )

    finalize_btn.click(
        finalize,
        inputs=[selection, analysis_state, slack_token, slack_ch, jira_srv, jira_usr, jira_tok, jira_proj],
        outputs=[final_out, status_out],
    )

    rag_btn.click(generate_rag_data, inputs=rag_files, outputs=rag_status)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
        share=False,
    )
