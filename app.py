import queue
import re
import threading

import gradio as gr

from src.llm.client import ClaudeClient, DEFAULT_MODEL
from src.mediator import Mediator
from src.utils.formatters import (
    format_customer_report,
    format_detailed_report,
    format_final_analysis,
)

ANSI_RE = re.compile(r'\033\[[0-9;]*m')

MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
    "claude-haiku-4-5-20251001",
    "gpt-4o",
    "gpt-4o-mini",
]

MODULE_MODEL_CHOICES = ["(same as main model)"] + MODELS

FORMATTERS = {
    "Standard":        format_final_analysis,
    "Detailed":        format_detailed_report,
    "Customer-facing": format_customer_report,
}


def _parse_weights(weights_str: str) -> dict:
    """Parse 'legal=2, market=0' into {'legal': 2.0, 'market': 0.0}."""
    weights = {}
    for part in weights_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Invalid weight '{part}' — expected format: module=number")
        name, val = part.split("=", 1)
        weights[name.strip()] = float(val.strip())
    return weights


def run_analysis(
    problem, model, module_model_choice, api_key,
    report_style, auto_select, no_search, deep_research,
    repeat_prompt, weights_str, tavily_key, user_context,
):
    if not problem.strip():
        yield "Please enter a problem.", "", gr.update(visible=False), None, None
        return
    if not api_key.strip():
        yield "Please enter your API key.", "", gr.update(visible=False), None, None
        return

    try:
        weights = _parse_weights(weights_str) if weights_str.strip() else {}
    except ValueError as e:
        yield str(e), "", gr.update(visible=False), None, None
        return

    key = api_key.strip()
    module_model = None if module_model_choice == "(same as main model)" else module_model_choice

    status_q = queue.Queue()

    def on_progress(msg):
        status_q.put(("status", msg))

    client = ClaudeClient(model=model, api_key=key)
    module_client = ClaudeClient(model=module_model, max_tokens=2048, api_key=key) if module_model else None
    mediator = Mediator(
        client,
        weights=weights,
        auto_select=auto_select,
        search=not no_search,
        deep_research=deep_research,
        module_client=module_client,
        repeat_prompt=repeat_prompt,
        tavily_api_key=tavily_key.strip() or None,
        on_progress=on_progress,
        user_context=user_context.strip() or None,
    )

    def run():
        try:
            result = mediator.analyze(problem)
            status_q.put(("done", result))
        except Exception as e:
            status_q.put(("error", str(e)))

    threading.Thread(target=run, daemon=True).start()

    log_lines = []
    while True:
        item = status_q.get()
        kind = item[0]

        if kind == "status":
            log_lines.append(item[1])
            yield "\n".join(log_lines), "", gr.update(visible=False), None, None

        elif kind == "error":
            yield f"Error: {item[1]}", "", gr.update(visible=False), None, None
            return

        elif kind == "done":
            result = item[1]
            formatter = FORMATTERS.get(report_style, format_final_analysis)
            report = ANSI_RE.sub('', formatter(result))

            q = result.quality
            tier_emoji = {"good": "✅", "degraded": "⚠️", "poor": "❌"}.get(q.tier if q else "", "")
            stats = ""
            if q:
                stats += f"{tier_emoji} **Quality:** {q.tier} ({q.score:.2f})&ensp;"
            if result.timing:
                stats += f"⏱ **Time:** {result.timing.total_s:.0f}s&ensp;"
            if result.token_usage:
                total_tok = result.token_usage.total_input + result.token_usage.total_output
                stats += f"🔢 **Tokens:** {total_tok:,}"

            yield report, stats, gr.update(visible=True), result, mediator
            return


def run_followup(question, result, mediator):
    if result is None or mediator is None:
        return "Run an analysis first."
    if not question.strip():
        return ""
    answer = mediator.followup(result, question.strip())
    return ANSI_RE.sub('', answer)


with gr.Blocks(title="Mediated Reasoning") as demo:
    result_state  = gr.State(None)
    mediator_state = gr.State(None)

    gr.Markdown("# 🧠 Mediated Reasoning\nMulti-perspective analysis via specialist AI modules.")
    gr.Markdown("_Bring your own API key — it is used only for your request and never stored._")

    with gr.Row():
        problem_input = gr.Textbox(
            label="Problem or idea",
            placeholder="Should we build a food delivery app?",
            lines=4,
            scale=3,
        )

    context_input = gr.Textbox(
        label="Your context (optional)",
        placeholder="e.g. Bootstrapped SaaS, 2 co-founders, $8k MRR, B2B — keeps recommendations actionable",
        lines=2,
    )

    with gr.Row():
        model_dd = gr.Dropdown(choices=MODELS, value=DEFAULT_MODEL, label="Model")
        module_model_dd = gr.Dropdown(
            choices=MODULE_MODEL_CHOICES,
            value="(same as main model)",
            label="Module model (optional)",
        )
        api_key_input = gr.Textbox(
            label="API key",
            placeholder="sk-ant-… for Claude · sk-… for GPT",
            type="password",
            scale=2,
        )

    with gr.Accordion("Advanced options", open=False):
        report_radio = gr.Radio(
            choices=["Standard", "Detailed", "Customer-facing"],
            value="Standard",
            label="Report style",
        )
        with gr.Row():
            auto_cb      = gr.Checkbox(label="Auto-select modules",  value=False)
            search_cb    = gr.Checkbox(label="Skip web search",       value=False)
            deep_cb      = gr.Checkbox(label="Deep research",         value=False)
            repeat_cb    = gr.Checkbox(label="Repeat prompt",         value=True)
        weights_input = gr.Textbox(
            label="Module weights (e.g. legal=2, market=0)",
            placeholder="legal=2, market=0.5",
            lines=1,
        )
        tavily_input = gr.Textbox(
            label="Tavily API key (optional — higher-quality search)",
            placeholder="tvly-…",
            type="password",
        )

    submit_btn = gr.Button("Analyze", variant="primary")
    stats_out  = gr.Markdown()
    report_out = gr.Textbox(label="Report", lines=40, interactive=False)

    with gr.Group(visible=False) as followup_group:
        gr.Markdown("---\n### Follow-up questions")
        followup_input = gr.Textbox(
            label="Ask a follow-up question",
            placeholder="What are the biggest legal risks?",
            lines=2,
        )
        followup_btn    = gr.Button("Ask")
        followup_answer = gr.Markdown()

    submit_btn.click(
        fn=run_analysis,
        inputs=[
            problem_input, model_dd, module_model_dd, api_key_input,
            report_radio, auto_cb, search_cb, deep_cb,
            repeat_cb, weights_input, tavily_input, context_input,
        ],
        outputs=[report_out, stats_out, followup_group, result_state, mediator_state],
    )

    followup_btn.click(
        fn=run_followup,
        inputs=[followup_input, result_state, mediator_state],
        outputs=[followup_answer],
    )

demo.launch()
