import queue
import re
import tempfile
import threading
from pathlib import Path
from typing import List, Optional

import gradio as gr

from src.llm.client import ClaudeClient
from src.mediator import Mediator
from src.project_memory import QAPair
from src.utils.document_loader import load_document, DocumentLoadError
from src.utils.formatters import (
    format_core_md,
    format_detail_md,
    format_sources_md,
)

ANSI_RE = re.compile(r'\033\[[0-9;]*m')

MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
    "gpt-4o",
    "gpt-4o-mini",
    "xai/grok-2",
    "xai/grok-3",
    "gemini/gemini-2.5-flash",
    "gemini/gemini-2.5-flash-lite",
    "gemini/gemini-2.5-pro",
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

/* ── Memory buttons — match input field height & font ── */
.memory-btns button {
    font-size: 0.875rem !important;
    height: 40px !important;
    min-height: 40px !important;
}

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
        "api-key":          "Your Anthropic / OpenAI / Google / xAI API key — never stored or shared",
        "memory-upload":     "Load a memory.md from a previous session to restore project context",
        "save-session":     "Download the current project memory as memory.md",
        "model-dd":         "LLM used for synthesis and the final report",
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
  <p class="fusen-sub">Experts debate, revise, and synthesize with live web search — business, career, research, strategy, and why the dinosaurs died out.</p>
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
def save_brief(brief_text: str):
    tmp = Path(tempfile.mkdtemp())
    brief_path = tmp / "memory.md"
    brief_path.write_text((brief_text or "").strip() + "\n", encoding="utf-8")
    return gr.update(visible=True, value=str(brief_path))


# ── Analysis ──────────────────────────────────────────────────────────────────
def run_analysis(
    problem, model, api_key,
    tavily_key,
    brief_text,
    document_path=None,
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

    document_context = None
    if document_path:
        try:
            document_context = load_document(document_path)
        except DocumentLoadError as e:
            yield _error(f"Document error: {e}"); return

    effective_context = ""
    if brief_text and brief_text.strip():
        effective_context = f"Project memory:\n{brief_text.strip()}"

    key      = api_key.strip()
    status_q = queue.Queue()

    def on_progress(msg):
        status_q.put(("status", msg))

    client   = ClaudeClient(model=model, api_key=key)
    mediator = Mediator(
        client, search=True,
        deep_research=True, agent_client=None,
        repeat_prompt=True,
        tavily_api_key=(tavily_key or "").strip() or None,
        on_progress=on_progress,
        user_context=effective_context or None,
        document_context=document_context,
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

    # ── Left Sidebar ──────────────────────────────────────────────────────────
    with gr.Sidebar(label="Settings", open=True, position="left", width=320,
                    elem_id="settings-sidebar"):

        api_key_input = gr.Textbox(
            label="API key", placeholder="sk-ant-… · sk-… · xai-…",
            type="password", elem_id="api-key",
        )
        model_dd = gr.Dropdown(
            choices=MODELS, value=MODELS[0], label="Model", elem_id="model-dd",
        )

        tavily_input = gr.Textbox(
            label="Tavily API key\n(optional)",
            placeholder="tvly-…", type="password", elem_id="tavily",
        )

        with gr.Row(elem_classes=["memory-btns"]):
            brief_upload = gr.UploadButton(
                "Load memory", file_types=[".md", ".txt"],
                type="filepath", elem_id="memory-upload",
            )
            save_memory_btn = gr.Button("Save memory", variant="secondary",
                                        elem_id="save-session")
        brief_load_info = gr.Markdown(visible=False)
        brief_download  = gr.File(show_label=False, visible=False,
                                  elem_id="memory-download")
        brief_area = gr.Textbox(visible=False, elem_id="memory")


    # ── Right Sidebar ─────────────────────────────────────────────────────────
    with gr.Sidebar(label="Detail", open=True, position="right", width=400,
                    elem_id="detail-sidebar"):
        right_stats_md  = gr.Markdown()
        right_detail_md = gr.Markdown("*Run an analysis to see details here.*")

    # ── Main canvas ───────────────────────────────────────────────────────────
    gr.HTML(_HEADER_HTML)

    problem_input = gr.Textbox(
        show_label=False,
        placeholder="Describe the problem, decision, or document you want analysed — e.g. Should I build a B2B SaaS for restaurant inventory management? · Upload your CV and ask: what are my strengths and gaps, what roles fit, and what salary range should I target?",
        lines=4, elem_id="problem",
    )
    document_upload = gr.File(
        label="+ (PDF, TXT, MD, DOCX, PPTX, XLSX)",
        file_types=[".pdf", ".txt", ".md", ".rst", ".docx", ".pptx", ".xlsx", ".xls"],
        type="filepath",
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

    # ── Wiring ────────────────────────────────────────────────────────────────
    def _load_brief(p):
        if not p:
            return "", gr.update(visible=False)
        return (
            Path(p).read_text(encoding="utf-8"),
            gr.update(visible=True, value=f"📄 {Path(p).name}"),
        )

    brief_upload.upload(
        fn=_load_brief, inputs=[brief_upload], outputs=[brief_area, brief_load_info],
    )

    submit_btn.click(
        fn=run_analysis,
        inputs=[
            problem_input, 
            model_dd, 
            api_key_input,
            tavily_input,
            brief_area,
            document_upload,
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
    save_memory_btn.click(
        fn=save_brief, inputs=[brief_area], outputs=[brief_download],
    )

demo.launch(server_name="0.0.0.0", server_port=7860, ssr_mode=False,
            theme=gr.themes.Soft(), css=_CSS, js=_JS)
