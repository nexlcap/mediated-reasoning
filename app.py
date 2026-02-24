import queue
import re
import threading
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import tkinter as _tk
    from tkinter import filedialog as _filedialog
    _TK_AVAILABLE = True
except ImportError:
    _TK_AVAILABLE = False

import gradio as gr

from src.llm.client import ClaudeClient
from src.mediator import Mediator
from src.project_memory import ProjectMemory, QAPair
from src.utils.formatters import (
    format_core_md,
    format_detail_md,
    format_sources_md,
)

PROJECTS_DIR = Path.home() / ".fusen" / "projects"
ANSI_RE = re.compile(r'\033\[[0-9;]*m')

MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
    "gpt-4o",
    "gpt-4o-mini",
    "xai/grok-2",
    "xai/grok-3",
]

# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

body,
.gradio-container,
.gradio-container p,
.gradio-container label,
.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container button,
.gradio-container h1,
.gradio-container h2,
.gradio-container h3,
.gradio-container h4 {
    font-family: 'Inter', ui-sans-serif, system-ui, -apple-system,
                 BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* ── App header ── */
.fusen-header { padding: 20px 0 8px 0; }
.fusen-title {
    font-size: 1.9em;
    font-weight: 700;
    background: linear-gradient(135deg, #f97316 0%, #ec4899 45%, #8b5cf6 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    display: inline-block;
    margin: 0 0 4px 0;
    line-height: 1.2;
}
.fusen-sub    { color: var(--body-text-color-subdued, #777); font-size: 0.9em;  margin: 2px 0 0 0; }
.fusen-tagline{ color: var(--body-text-color-subdued, #aaa); font-size: 0.82em; font-style: italic; margin: 1px 0 0 0; }

/* ── Analyze button ── */
.analyze-btn button {
    background: linear-gradient(135deg, #f97316 0%, #ec4899 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}
.analyze-btn button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(249, 115, 22, 0.35) !important;
}

/* ── Shared keyframes ── */
@keyframes statusFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0);   }
}
@keyframes dotPulse {
    0%, 100% { opacity: 1;   }
    50%       { opacity: 0.2; }
}
@keyframes gradientShift {
    0%   { background-position: 0%   50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0%   50%; }
}

/* ── Pipeline animation ── */
.pipe-header {
    background: linear-gradient(270deg, #f97316, #ec4899, #8b5cf6, #3b82f6);
    background-size: 400% 400%;
    animation: gradientShift 3s ease infinite;
    color: white;
    padding: 10px 16px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.88em;
    letter-spacing: 0.03em;
    margin-bottom: 14px;
}
.pipeline { padding: 4px 0; }
.pipe-step {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 4px;
    animation: statusFadeIn 0.4s ease both;
    border-bottom: 1px solid var(--border-color-primary, #e5e7eb);
}
.pipe-step:last-child { border-bottom: none; }
.pipe-dot {
    width: 9px; height: 9px;
    border-radius: 50%;
    margin-top: 4px;
    flex-shrink: 0;
    background: #d1d5db;
}
.pipe-done  .pipe-dot { background: #22c55e; }
.pipe-active .pipe-dot {
    background: #f97316;
    animation: dotPulse 1s ease infinite;
    box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.18);
}
.pipe-text       { font-size: 0.85em; line-height: 1.45; color: var(--body-text-color, #333); }
.pipe-done .pipe-text { color: var(--body-text-color-subdued, #999); }
.status-error {
    color: #dc2626;
    padding: 8px 12px;
    border-left: 3px solid #dc2626;
    font-size: 0.9em;
}

/* ── Follow-up area ── */
.follow-qa-area { margin-top: 8px; }
.follow-qa-area p { line-height: 1.65; }
.followup-row {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color-primary, #e5e7eb);
    align-items: flex-end !important;
}

/* ── Resizable sidebars ──
   overflow is applied only when .open so the absolutely-positioned
   toggle button (left:100% when closed) is never clipped. ── */
#settings-sidebar.open {
    resize: horizontal !important;
    overflow: auto !important;
    min-width: 200px !important;
    max-width: 650px !important;
}
#detail-sidebar.open {
    direction: rtl !important;
    resize: horizontal !important;
    overflow: auto !important;
    min-width: 200px !important;
    max-width: 650px !important;
}
#detail-sidebar.open > * { direction: ltr !important; }

/* ── Modals ── */
.modal-overlay > div.gr-group,
.modal-overlay {
    position: fixed !important;
    inset: 0 !important;
    background: rgba(0, 0, 0, 0.55) !important;
    z-index: 9999 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
}
.modal-inner {
    background: var(--background-fill-primary, white) !important;
    border-radius: 12px !important;
    padding: 28px !important;
    width: 65vw !important;
    max-width: 900px !important;
    min-width: 380px !important;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4) !important;
    position: relative !important;
    inset: unset !important;
}
"""

# ── JavaScript: add title-attribute tooltips after Gradio renders ─────────────
_JS = """
function() {
    const TIPS = {
        "api-key":          "Your Anthropic / OpenAI / xAI API key — never stored or shared",
        "context":          "Background about your situation (stage, budget, constraints) — prepended to every analysis",
        "context-expand":   "Open in a larger editing window",
        "projects-dd":      "Pick an existing project to load its accumulated brief",
        "create-new-cb":    "Enable to save this session under a new named project",
        "project-name":     "Name for the new project folder (letters, numbers, hyphens)",
        "save-location":    "Parent directory where the project folder will be created (default: ~/.fusen/projects/)",
        "browse-save":      "Open the system folder picker to choose a save location",
        "custom-path":      "Full path to any folder — load or create a project there regardless of the named-project system",
        "browse-open":      "Open the system folder picker to choose a project folder",
        "load-btn":         "Load the project brief from disk, or create the folder and a blank brief if it doesn't exist yet",
        "brief":            "Living one-page project summary — rewritten by the AI after each session, always editable by you",
        "brief-expand":     "Open in a larger editing window",
        "save-session":     "Append this session to the log and ask the AI to rewrite the project brief",
        "model-dd":         "LLM used for synthesis and the final report",
        "agent-model-dd":   "LLM used for individual specialist agents — set to a cheaper/faster model to reduce cost without affecting synthesis quality",
        "auto-cb":          "Let the AI choose the most relevant specialist lenses for your specific problem",
        "search-cb":        "Disable web search — runs faster but recommendations won't cite live sources",
        "deep-cb":          "Run an extra conflict-resolution pass to reconcile disagreements between specialists",
        "repeat-cb":        "Re-send the original question to synthesis — measurably improves quality (arxiv 2512.14982)",
        "tavily":           "Optional Tavily premium search key — higher-quality citations than the default DuckDuckGo fallback",
        "problem":          "State the problem, idea, or decision you want analysed from multiple expert angles",
        "analyze-btn":      "Run a full multi-specialist analysis (typically 30–120 s depending on model and depth)",
        "show-detail":      "Load the specialist-by-specialist breakdown into the right sidebar",
        "show-qa":          "Load the full follow-up Q&A history into the right sidebar",
        "followup":         "Ask a follow-up question — the analysis context is kept so answers are grounded",
        "followup-btn":     "Send your follow-up question"
    };
    function applyTips() {
        for (const [id, tip] of Object.entries(TIPS)) {
            const el = document.getElementById(id);
            if (el) el.title = tip;
        }
    }
    applyTips();
    setTimeout(applyTips, 800);
    setTimeout(applyTips, 3000);
}
"""

_HEADER_HTML = """
<div class="fusen-header">
  <div class="fusen-title">🔥 Fusen</div>
  <p class="fusen-sub">AI co-founder for solo entrepreneurs — fuse every angle, move alone.</p>
  <p class="fusen-tagline">Let the journey begin!</p>
</div>
"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def _parse_weights(weights_str: str) -> dict:
    weights = {}
    for part in weights_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid weight '{part}' — expected format: agent=number")
        name, val = part.split("=", 1)
        weights[name.strip()] = float(val.strip())
    return weights


def browse_for_folder() -> str:
    if not _TK_AVAILABLE:
        return ""
    try:
        root = _tk.Tk()
        root.withdraw()
        root.wm_attributes("-topmost", True)
        folder = _filedialog.askdirectory(title="Select project folder")
        root.destroy()
        return folder or ""
    except Exception:
        return ""


def _list_projects() -> List[str]:
    if not PROJECTS_DIR.exists():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir())


def _status_html(lines: List[str]) -> str:
    if not lines:
        return ""
    steps = "".join(
        f'<div class="pipe-step {"pipe-active" if i == len(lines)-1 else "pipe-done"}"'
        f' style="animation-delay:{min(i * 0.12, 2.0):.2f}s">'
        f'<div class="pipe-dot"></div>'
        f'<div class="pipe-text">{line}</div>'
        f'</div>'
        for i, line in enumerate(lines)
    )
    return (
        f'<div class="pipeline">'
        f'<div class="pipe-header">✦ Analysing your question…</div>'
        f'{steps}</div>'
    )


def _format_follow_qa_md(qa_history: List[QAPair]) -> str:
    if not qa_history:
        return ""
    return "\n\n".join(f"---\n\n**You:** {q}\n\n{a}" for q, a in qa_history)


def _format_qa_right(qa_history: List[QAPair]) -> str:
    if not qa_history:
        return "*No follow-up questions yet.*"
    md = "### Follow-up history\n\n"
    for i, (q, a) in enumerate(qa_history, 1):
        md += f"**Q{i}.** {q}\n\n{a}\n\n---\n\n"
    return md


def _show_detail_in_sidebar(result) -> str:
    if result is None:
        return "*No analysis yet — run an analysis first.*"
    try:
        return format_detail_md(result, detailed=False)
    except Exception as e:
        return f"*Error loading detail: {e}*"


def _show_qa_in_sidebar(qa_history) -> str:
    try:
        return _format_qa_right(qa_history or [])
    except Exception as e:
        return f"*Error: {e}*"


# ── Project helpers ───────────────────────────────────────────────────────────
def load_project(selected_name: str, new_name: str, save_location: str, custom_path: str) -> Tuple:
    custom_path = (custom_path or "").strip()
    if custom_path:
        project_dir  = Path(custom_path).expanduser().resolve()
        display_name = project_dir.name
    else:
        name = (new_name or selected_name or "").strip()
        name = re.sub(r"[^\w\- ]", "", name).strip()
        if not name:
            return "", "Enter a project name, paste a path, or select an existing one.", None, gr.update()
        parent = (
            Path((save_location or "").strip()).expanduser().resolve()
            if (save_location or "").strip() else PROJECTS_DIR
        )
        project_dir  = parent / name
        display_name = name
    try:
        is_new = not project_dir.exists()
        pm     = ProjectMemory(str(project_dir))
        brief  = pm.load()
        verb   = "Created" if is_new else "Loaded"
        return (
            brief,
            f"{verb}: **{display_name}**  (`{project_dir}`)",
            pm,
            gr.update(choices=_list_projects(), value=display_name if not custom_path else None),
        )
    except Exception as e:
        return "", f"Error: {e}", None, gr.update()


def save_project_session(
    result, mediator, qa_history: List[QAPair],
    project_memory: Optional[ProjectMemory],
    api_key: str, model: str,
) -> Tuple[str, str]:
    if project_memory is None:
        return "", "No project loaded."
    if result is None:
        return "", "Run an analysis first."
    try:
        project_memory.save_session(result, qa_history or [])
        client    = ClaudeClient(model=model, api_key=api_key.strip() or None)
        new_brief = project_memory.update_brief(client, result, qa_history or [])
        return new_brief or "", "Session saved and brief updated."
    except Exception as e:
        return "", f"Error saving session: {e}"


# ── Analysis ──────────────────────────────────────────────────────────────────
def run_analysis(
    problem, model, agent_model, api_key,
    auto_select, no_search, deep_research,
    repeat_prompt, tavily_key, user_context,
    project_memory, brief_text,
):
    # 10 outputs: status_html · core_out · right_detail_md · right_stats_md
    #             status_group · results_group · follow_qa_md
    #             result_state · mediator_state · qa_history_state

    def _progress(log_lines):
        return (_status_html(log_lines), "", "", "",
                gr.update(visible=True), gr.update(visible=False), "",
                None, None, [])

    def _error(msg):
        return (f"<div class='status-error'>⚠ {msg}</div>", "", "", "",
                gr.update(visible=True), gr.update(visible=False), "",
                None, None, [])

    if not problem.strip():
        yield _error("Please enter a problem."); return
    if not api_key.strip():
        yield _error("Please enter your API key."); return

    effective_context = (user_context or "").strip()
    if project_memory is not None and brief_text and brief_text.strip():
        brief_ctx = f"Project brief:\n{brief_text.strip()}"
        effective_context = brief_ctx + ("\n\n" + effective_context if effective_context else "")

    key      = api_key.strip()
    status_q = queue.Queue()

    def on_progress(msg):
        status_q.put(("status", msg))

    client       = ClaudeClient(model=model, api_key=key)
    agent_client = ClaudeClient(model=agent_model, api_key=key) if agent_model != model else None
    mediator     = Mediator(
        client, weights={},
        auto_select=auto_select, search=not no_search,
        deep_research=deep_research, agent_client=agent_client,
        repeat_prompt=repeat_prompt,
        tavily_api_key=(tavily_key or "").strip() or None,
        on_progress=on_progress,
        user_context=effective_context or None,
    )

    def run():
        try:
            status_q.put(("done", mediator.analyze(problem)))
        except BaseException as e:
            status_q.put(("error", str(e)))

    threading.Thread(target=run, daemon=True).start()

    log_lines = []
    while True:
        try:
            item = status_q.get(timeout=5)
        except Exception:
            if not threading.active_count():
                yield _error("Analysis thread exited unexpectedly."); return
            continue

        kind = item[0]
        if kind == "status":
            log_lines.append(item[1])
            yield _progress(log_lines)
        elif kind == "error":
            yield _error(item[1]); return
        elif kind == "done":
            result    = item[1]
            core_md   = format_core_md(result)
            detail_md = format_detail_md(result, detailed=False)
            q         = result.quality
            te        = {"good": "✅", "degraded": "⚠️", "poor": "❌"}.get(q.tier if q else "", "")
            stats     = ""
            if q:
                stats += f"{te} **Quality:** {q.tier} ({q.score:.2f})&ensp;"
            if result.timing:
                stats += f"⏱ **Time:** {result.timing.total_s:.0f}s&ensp;"
            if result.token_usage:
                stats += f"🔢 **Tokens:** {result.token_usage.total_input + result.token_usage.total_output:,}"
            sources_md = format_sources_md(result)
            right_top  = stats + ("\n\n---\n\n" + sources_md if sources_md else "")
            yield ("", core_md, detail_md, right_top,
                   gr.update(visible=False), gr.update(visible=True), "",
                   result, mediator, [])
            return


def run_followup(question, result, mediator, qa_history: List[QAPair]):
    history = list(qa_history or [])
    if result is None or mediator is None:
        return _format_follow_qa_md(history), history, question, gr.update()
    if not question.strip():
        return _format_follow_qa_md(history), history, "", gr.update()
    answer  = mediator.followup(result, question.strip())
    updated = history + [(question.strip(), ANSI_RE.sub('', answer))]
    return _format_follow_qa_md(updated), updated, "", _format_qa_right(updated)


# ── UI ────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="Fusen") as demo:
    result_state      = gr.State(None)
    mediator_state    = gr.State(None)
    qa_history_state  = gr.State([])
    project_mem_state = gr.State(None)

    # ── Left Sidebar ──────────────────────────────────────────────────────────
    with gr.Sidebar(label="Settings", open=True, position="left", width=320,
                    elem_id="settings-sidebar"):

        api_key_input = gr.Textbox(
            label="API key", placeholder="sk-ant-… · sk-… · xai-…",
            type="password", elem_id="api-key",
        )
        context_input = gr.Textbox(
            label="Additional context (optional)",
            placeholder="e.g. Bootstrapped SaaS, 2 co-founders, $8k MRR, B2B — keeps recommendations actionable",
            lines=2, elem_id="context",
        )
        context_expand_btn = gr.Button("⤢ Expand", size="sm", variant="secondary",
                                       elem_id="context-expand")

        with gr.Accordion("Project memory (optional)", open=False):
            with gr.Tabs():
                with gr.Tab("Named project"):
                    existing_projects_dd = gr.Dropdown(
                        label="Existing projects", choices=_list_projects(),
                        value=None, allow_custom_value=False, elem_id="projects-dd",
                    )
                    create_new_cb = gr.Checkbox(label="Save as new project", value=False,
                                               elem_id="create-new-cb")
                    with gr.Group(visible=False) as new_project_group:
                        new_project_name = gr.Textbox(
                            label="Project name", placeholder="my-saas-idea",
                            elem_id="project-name",
                        )
                        with gr.Row():
                            save_location_input = gr.Textbox(
                                label="Save in", placeholder=str(PROJECTS_DIR),
                                scale=3, elem_id="save-location",
                            )
                            browse_save_btn = gr.Button("Browse…", scale=1,
                                                        elem_id="browse-save")
                with gr.Tab("Any folder"):
                    with gr.Row():
                        custom_path_input = gr.Textbox(
                            label="Folder path",
                            placeholder="/home/you/projects/my-startup",
                            interactive=True, scale=4, elem_id="custom-path",
                        )
                        browse_open_btn = gr.Button("Browse…", scale=1,
                                                    elem_id="browse-open")

            load_project_btn = gr.Button("Load / Create", variant="primary",
                                         elem_id="load-btn")
            project_status = gr.Markdown()
            brief_area = gr.Textbox(
                label="Project brief (auto-updated after each session, human-editable)",
                lines=8, interactive=True, elem_id="brief",
            )
            brief_expand_btn = gr.Button("⤢ Expand", size="sm", variant="secondary",
                                         elem_id="brief-expand")
            with gr.Row():
                save_session_btn = gr.Button("Save session + update brief",
                                             elem_id="save-session")
                save_status = gr.Markdown()

        with gr.Accordion("Advanced options", open=False):
            model_dd = gr.Dropdown(
                choices=MODELS, value=MODELS[0], label="Synthesis model", elem_id="model-dd",
            )
            agent_model_dd = gr.Dropdown(
                choices=MODELS, value=MODELS[0], label="Agent model", elem_id="agent-model-dd",
            )
            auto_cb   = gr.Checkbox(label="Auto-select agents", value=True,  elem_id="auto-cb")
            search_cb = gr.Checkbox(label="Skip web search",     value=False, elem_id="search-cb")
            deep_cb   = gr.Checkbox(label="Deep research",       value=True,  elem_id="deep-cb")
            repeat_cb = gr.Checkbox(label="Repeat prompt",       value=True,  elem_id="repeat-cb")
            tavily_input = gr.Textbox(
                label="Tavily API key (optional — higher-quality search)",
                placeholder="tvly-…", type="password", elem_id="tavily",
            )

    # ── Right Sidebar ─────────────────────────────────────────────────────────
    with gr.Sidebar(label="Detail", open=True, position="right", width=400,
                    elem_id="detail-sidebar"):
        right_stats_md  = gr.Markdown()
        right_detail_md = gr.Markdown("*Run an analysis to see details here.*")

    # ── Main canvas ───────────────────────────────────────────────────────────
    gr.HTML(_HEADER_HTML)

    problem_input = gr.Textbox(
        show_label=False,
        placeholder="Describe the problem or idea you want to analyse — e.g. Should I build a B2B SaaS for restaurant inventory management?",
        lines=4, elem_id="problem",
    )
    submit_btn = gr.Button("Analyze", variant="primary", size="lg",
                           elem_classes=["analyze-btn"], elem_id="analyze-btn")

    with gr.Group(visible=False) as status_group:
        status_html = gr.HTML()

    with gr.Group(visible=False) as results_group:
        core_out = gr.Markdown()
        with gr.Row():
            show_detail_btn = gr.Button("📊 Analysis detail",   size="sm",
                                        variant="secondary", elem_id="show-detail")
            show_qa_btn     = gr.Button("💬 Follow-up history", size="sm",
                                        variant="secondary", elem_id="show-qa")

        follow_qa_md = gr.Markdown("", elem_classes=["follow-qa-area"])

        with gr.Row(elem_classes=["followup-row"]):
            followup_input = gr.Textbox(
                show_label=False, placeholder="Ask a follow-up question…",
                lines=1, scale=9, elem_id="followup",
            )
            followup_btn = gr.Button("↵", scale=1, variant="secondary",
                                     elem_id="followup-btn")

    # ── Modals ────────────────────────────────────────────────────────────────
    with gr.Group(visible=False, elem_classes=["modal-overlay"]) as context_modal:
        with gr.Column(elem_classes=["modal-inner"]):
            gr.Markdown("### Additional context")
            context_modal_text = gr.Textbox(
                show_label=False, lines=18, interactive=True,
                placeholder="e.g. Bootstrapped SaaS, 2 co-founders, $8k MRR, B2B — keeps recommendations actionable",
            )
            with gr.Row():
                context_modal_save_btn   = gr.Button("Save & Close", variant="primary")
                context_modal_cancel_btn = gr.Button("Cancel")

    with gr.Group(visible=False, elem_classes=["modal-overlay"]) as brief_modal:
        with gr.Column(elem_classes=["modal-inner"]):
            gr.Markdown("### Project brief")
            brief_modal_text = gr.Textbox(show_label=False, lines=22, interactive=True)
            with gr.Row():
                brief_modal_save_btn   = gr.Button("Save & Close", variant="primary")
                brief_modal_cancel_btn = gr.Button("Cancel")

    # ── Wiring ────────────────────────────────────────────────────────────────
    create_new_cb.change(
        fn=lambda c: gr.update(visible=c), inputs=[create_new_cb], outputs=[new_project_group],
    )
    browse_save_btn.click(fn=browse_for_folder, inputs=[], outputs=[save_location_input])
    browse_open_btn.click(fn=browse_for_folder, inputs=[], outputs=[custom_path_input])

    load_project_btn.click(
        fn=load_project,
        inputs=[existing_projects_dd, new_project_name, save_location_input, custom_path_input],
        outputs=[brief_area, project_status, project_mem_state, existing_projects_dd],
    )

    submit_btn.click(
        fn=run_analysis,
        inputs=[
            problem_input, model_dd, agent_model_dd, api_key_input,
            auto_cb, search_cb, deep_cb,
            repeat_cb, tavily_input, context_input,
            project_mem_state, brief_area,
        ],
        outputs=[
            status_html, core_out, right_detail_md, right_stats_md,
            status_group, results_group, follow_qa_md,
            result_state, mediator_state, qa_history_state,
        ],
    )

    _fu_in  = [followup_input, result_state, mediator_state, qa_history_state]
    _fu_out = [follow_qa_md, qa_history_state, followup_input, right_detail_md]

    followup_btn.click(fn=run_followup, inputs=_fu_in, outputs=_fu_out)
    followup_input.submit(fn=run_followup, inputs=_fu_in, outputs=_fu_out)

    show_detail_btn.click(
        fn=_show_detail_in_sidebar, inputs=[result_state], outputs=[right_detail_md],
    )
    show_qa_btn.click(
        fn=_show_qa_in_sidebar, inputs=[qa_history_state], outputs=[right_detail_md],
    )
    save_session_btn.click(
        fn=save_project_session,
        inputs=[result_state, mediator_state, qa_history_state,
                project_mem_state, api_key_input, model_dd],
        outputs=[brief_area, save_status],
    )

    context_expand_btn.click(
        fn=lambda v: (gr.update(visible=True), v),
        inputs=[context_input], outputs=[context_modal, context_modal_text],
    )
    context_modal_save_btn.click(
        fn=lambda v: (v, gr.update(visible=False)),
        inputs=[context_modal_text], outputs=[context_input, context_modal],
    )
    context_modal_cancel_btn.click(
        fn=lambda: gr.update(visible=False), inputs=[], outputs=[context_modal],
    )
    brief_expand_btn.click(
        fn=lambda v: (gr.update(visible=True), v),
        inputs=[brief_area], outputs=[brief_modal, brief_modal_text],
    )
    brief_modal_save_btn.click(
        fn=lambda v: (v, gr.update(visible=False)),
        inputs=[brief_modal_text], outputs=[brief_area, brief_modal],
    )
    brief_modal_cancel_btn.click(
        fn=lambda: gr.update(visible=False), inputs=[], outputs=[brief_modal],
    )

demo.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False,
            theme=gr.themes.Soft(), css=_CSS, js=_JS)
