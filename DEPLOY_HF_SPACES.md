# Deploying to Hugging Face Spaces

This app is a Gradio app, which Hugging Face Spaces supports natively (free CPU tier
available). Below are two ways to deploy: via the web UI (no git needed) or via git.

---

## Option A: Web UI Upload (fastest, no git/CLI needed)

1. Go to https://huggingface.co/new-space
2. Sign in / create a free Hugging Face account if you don't have one.
3. Fill in the form:
   - **Owner**: your username (or an organization)
   - **Space name**: e.g. `incident-response-platform`
   - **License**: MIT (or your choice)
   - **Select the Space SDK**: **Gradio**
   - **Space hardware**: `CPU basic` (free) is fine to start
   - **Visibility**: Public or Private (Private requires a paid plan for some features,
     but private Spaces on the free CPU tier are available)
4. Click **Create Space**.
5. On the new (empty) Space page, click **Files → Add file → Upload files**.
6. Upload these files from this conversation's output folder:
   - `app.py`
   - `requirements.txt`
   - `README.md`  (contains the Space's YAML config — **important**, don't skip)
   - `incidents_rag.csv` (optional sample RAG knowledge base)
   - `.gitignore` (optional)
7. Commit the upload (commit message can be anything, e.g. "Initial deploy").
8. The Space will automatically build. Watch the **Logs** tab — first build takes
   ~2-5 minutes while it installs `requirements.txt`.
9. Once it shows **Running**, configure secrets (see below), then it's live at:
   `https://huggingface.co/spaces/<your-username>/<space-name>`

---

## Option B: Git Push

```bash
# 1. Install the HF CLI (optional, but handy for auth)
pip install -U "huggingface_hub[cli]"
huggingface-cli login   # paste a token with "write" access from
                         # https://huggingface.co/settings/tokens

# 2. Create the Space (or do it via the web UI as in Option A, step 1-4)
huggingface-cli repo create incident-response-platform --type space --space_sdk gradio

# 3. Clone it locally
git clone https://huggingface.co/spaces/<your-username>/incident-response-platform
cd incident-response-platform

# 4. Copy in the app files (app.py, requirements.txt, README.md, incidents_rag.csv)
cp /path/to/app.py /path/to/requirements.txt /path/to/README.md /path/to/incidents_rag.csv .

# 5. Commit and push
git add .
git commit -m "Initial deploy"
git push
```

The Space rebuilds automatically on every push to the `main` branch.

---

## Configure Secrets (required for Slack/JIRA/LLM)

1. Open your Space → **Settings** tab → **Variables and secrets**.
2. Click **New secret** for each of the following (only add the ones you need):

   | Name | Example value |
   |---|---|
   | `OPENAI_API_KEY` | `sk-...` (or use `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` instead) |
   | `SLACK_BOT_TOKEN` | `xoxb-...` |
   | `SLACK_CHANNEL` | `#incidents` |
   | `JIRA_SERVER` | `https://your-domain.atlassian.net` |
   | `JIRA_USERNAME` | `you@company.com` |
   | `JIRA_API_TOKEN` | `your-jira-api-token` |
   | `JIRA_PROJECT_KEY` | `OPS` |
   | `TAVILY_API_KEY` | `tvly-...` (optional, enables web search) |

3. After adding/changing secrets, the Space restarts automatically (or click
   **Restart this Space** under the Settings → Factory reboot / Restart option).

**Note:** Secrets are encrypted and not visible to visitors, and are not shown in
the Space's public files — they're only injected as environment variables at
runtime, which is exactly how `app.py` reads them (`os.environ.get(...)`).

---

## After Deploy: Quick Checklist

- [ ] Space shows status **Running** (Settings/Logs tab, no build errors)
- [ ] Secrets added for your LLM provider (`OPENAI_API_KEY`, etc.)
- [ ] Secrets added for Slack (`SLACK_BOT_TOKEN`, `SLACK_CHANNEL`)
- [ ] Secrets added for JIRA (`JIRA_SERVER`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, `JIRA_PROJECT_KEY`)
- [ ] Slack bot invited to the target channel (`/invite @YourBotName` in Slack)
- [ ] Open the Space URL, paste a sample incident, click **Run Analysis**
- [ ] Pick a remediation, click **🚀 Use Selected → Send to Slack & JIRA**
- [ ] Confirm message appears in Slack and ticket appears in JIRA

---

## Notes & Gotchas

- **`TypeError: unhashable type: 'dict'` from `jinja2/utils.py` via
  `Jinja2Templates.TemplateResponse` (also surfaces as the misleading
  `ValueError: ...set share=True`)**: gradio 4.44.1's `routes.py` calls the
  **old** Starlette signature `TemplateResponse(name, context)`. Newer Starlette
  releases removed that shim and require `TemplateResponse(request, name,
  context)` — with the old call, the `context` dict lands in the `name` slot,
  and Jinja2 chokes trying to use a dict as part of its template-cache key. That
  500s `/`, which makes `demo.launch()`'s health-check fail and report the
  unrelated-looking `share=True` error.
  **Fix (two layers, both already applied)**:
  1. `requirements.txt` pins `starlette<0.41` (paired with `fastapi<0.113.0`,
     which HF's builder also appends) — a version range that should still have
     the old-style shim.
  2. `app.py` also includes a small compatibility shim for
     `Jinja2Templates.TemplateResponse` that detects the new
     `(request, name, context)` signature and transparently rewrites old-style
     `(name, context)` calls to it — this is a no-op if the pin above already
     gives you an old Starlette, and a safety net if something else pulls in a
     newer one transitively.
- **`TypeError: argument of type 'bool' is not iterable` + `ValueError: When
  localhost is not accessible... set share=True`**: these two errors are linked.
  Some `gradio_client` versions crash converting a JSON-Schema boolean
  (`additionalProperties: true`, used for `gr.State`'s "any type" schema) because
  their converter assumes every schema is a dict. That crash makes the `/` route
  500, which makes `demo.launch()`'s own startup health-check fail — and gradio
  reports *that* as "localhost not accessible, set share=True" (a red herring).
  **Fix**: `app.py` now includes a small monkeypatch right after `import gradio as gr`
  that makes the schema converter treat boolean schemas as `"Any"` instead of
  crashing. No version pins needed for this one. `demo.launch()` is also called
  with explicit `server_name="0.0.0.0"`, `server_port` (from `$PORT` or 7860), and
  `share=False`.
- **Looping between `MultimodalTextbox file_count` error and `HfFolder` import
  error**: these two errors come from opposite ends of the same problem —
  - `gradio==4.36.0` lacks the `file_count` kwarg on `MultimodalTextbox`.
  - `gradio==4.44.1` (or later) supports `file_count`, but its own
    `requirements.txt` has **no upper bound** on `huggingface_hub`, so pip
    installs the latest `huggingface_hub` (0.26+), which removed the
    `HfFolder`/`whoami` symbols that gradio's `oauth.py` still imports.

  **Fix**: pin **both together** — `requirements.txt` now has:
  ```
  gradio==4.44.1
  huggingface_hub==0.25.2
  ```
  4.44.1 supports `file_count`, and 0.25.2 still provides `HfFolder`, so both
  errors are resolved at once. Make sure `README.md`'s `sdk_version: 4.44.1`
  still matches. Trigger a rebuild (push a commit or
  Settings → Factory reboot) after updating.
- **`pyaudioop` / `ModuleNotFoundError: audioop` build error**: this happens when
  the Space builds with Python 3.13, where the `audioop` stdlib module was removed
  and one of Gradio's transitive deps (`pydub`, used for audio components) can't
  resolve. **Fix**: the `README.md` in this repo already pins
  `python_version: "3.11"` in its YAML front-matter — make sure that line is
  present, then go to your Space → **Settings → Factory reboot** (or just push a
  commit) to force a clean rebuild on Python 3.11.
- **Free CPU Spaces sleep after inactivity** and wake on the next visit (a ~30-60s
  cold start). Upgrade to a paid persistent CPU if you need always-on.
- **Don't put real API keys in `app.py` or commit them to the repo** — always use
  Space secrets. The app already reads everything from `os.environ`.
- If you change `requirements.txt`, the Space automatically rebuilds the
  environment on the next push/restart.
- The **RAG** tab lets you upload `incidents_rag.csv` (or your own docs) at runtime —
  you don't need to bake it into the repo, though including it as a sample is fine.
- If the build fails, check the **Logs** tab for the exact pip/install error —
  usually a version conflict in `requirements.txt`.
