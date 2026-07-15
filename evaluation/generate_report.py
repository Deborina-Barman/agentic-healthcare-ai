from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.evaluate_nlice import evaluate_nlice_extraction
from evaluation.evaluate_retrieval import evaluate_retrieval
from evaluation.evaluate_summary import evaluate_summary
from evaluation.evaluate_urgency import evaluate_urgency
from evaluation.evaluate_ocr import evaluate_ocr
from evaluation.evaluate_conversation import evaluate_conversation
from evaluation.evaluate_latency import evaluate_latency
from evaluation.evaluate_tokens import evaluate_tokens

RESULTS_DIR = BASE_DIR / "results"
REPORT_PATH = RESULTS_DIR / "evaluation_report.md"


def _format_value(value: Any, *, skipped: bool = False) -> str:
    if skipped:
        return "Evaluation skipped"
    if value is None:
        return "unavailable"
    return str(value)


def _append_section(report_lines: list[str], title: str, result: dict[str, Any]) -> None:
    report_lines.append(f"## {title}")
    report_lines.append("")
    report_lines.append(f"- Status: {result.get('status', 'skipped')}")
    functions_called = result.get("production_functions_called", [])
    if functions_called:
        report_lines.append(f"- Production functions called: {', '.join(functions_called)}")
    skipped_reason = result.get("skipped_reason")
    if skipped_reason:
        report_lines.append(f"- Skipped reason: {skipped_reason}")
    report_lines.append("")


def generate_report() -> str:
    nlice = evaluate_nlice_extraction()
    retrieval = evaluate_retrieval()
    summary = evaluate_summary()
    urgency = evaluate_urgency()
    ocr = evaluate_ocr()
    conversation = evaluate_conversation()
    latency = evaluate_latency()
    tokens = evaluate_tokens()

    report_lines: list[str] = []
    report_lines.append("# SevaCare AI Evaluation Report")
    report_lines.append("")
    report_lines.append("## Overview")
    report_lines.append("")
    report_lines.append("- This report attempts to exercise the real SevaCare production pipeline whenever the required runtime and API dependencies are available.")
    report_lines.append("- Fixture JSON files are treated as labeled inputs only; they are not used as fabricated metrics.")
    report_lines.append(f"- NLICE evaluation cases: {nlice.get('dataset_size', 0)}")
    report_lines.append(f"- Retrieval evaluation cases: {retrieval.get('case_count', 0)}")
    report_lines.append(f"- Summary evaluation cases: {summary.get('case_count', 0)}")
    report_lines.append(f"- OCR evaluation cases: {ocr.get('case_count', 0)}")
    report_lines.append(f"- Conversation evaluation cases: {conversation.get('case_count', 0)}")
    report_lines.append("")

    _append_section(report_lines, "NLICE Metrics", nlice)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    metrics = nlice.get("metrics", {})
    for name in ("accuracy", "precision", "recall", "f1"):
        value = metrics.get(name)
        report_lines.append(f"| {name} | {_format_value(value, skipped=nlice.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "Retrieval Metrics", retrieval)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    for name in ("precision_at_1", "precision_at_3", "recall_at_3", "hit_at_3", "mrr"):
        value = retrieval.get(name)
        report_lines.append(f"| {name} | {_format_value(value, skipped=retrieval.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "Summary Metrics", summary)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    summary_stats = summary.get("summary_stats", {})
    for name in ("complaint_captured", "duration_captured", "medication_captured", "medication_response_captured", "negative_findings_correct", "hallucinated_findings", "overall_factual_correctness"):
        value = summary_stats.get(name)
        report_lines.append(f"| {name} | {_format_value(value, skipped=summary.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "Urgency Metrics", urgency)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    for name in ("accuracy", "precision", "recall", "f1"):
        value = urgency.get(name)
        report_lines.append(f"| {name} | {_format_value(value, skipped=urgency.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "OCR Metrics", ocr)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    report_lines.append(f"| extraction_accuracy | {_format_value(ocr.get('extraction_accuracy'), skipped=ocr.get('status') == 'skipped')} |")
    report_lines.append(f"| missing_fields | {_format_value(ocr.get('missing_fields'), skipped=ocr.get('status') == 'skipped')} |")
    report_lines.append(f"| incorrect_values | {_format_value(ocr.get('incorrect_values'), skipped=ocr.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "Conversation Completion", conversation)
    report_lines.append(f"- Completion rate: {_format_value(conversation.get('completion_rate'), skipped=conversation.get('status') == 'skipped')}")
    report_lines.append(f"- Completed cases: {conversation.get('completed_cases')} / {conversation.get('case_count')}")
    report_lines.append("")

    _append_section(report_lines, "Latency Statistics", latency)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    report_lines.append(f"| average_latency_seconds | {_format_value(latency.get('average_latency_seconds'), skipped=latency.get('status') == 'skipped')} |")
    report_lines.append(f"| min_latency_seconds | {_format_value(latency.get('min_latency_seconds'), skipped=latency.get('status') == 'skipped')} |")
    report_lines.append(f"| max_latency_seconds | {_format_value(latency.get('max_latency_seconds'), skipped=latency.get('status') == 'skipped')} |")
    report_lines.append("")

    _append_section(report_lines, "Token Usage", tokens)
    report_lines.append("| Metric | Value |")
    report_lines.append("| --- | --- |")
    report_lines.append(f"| average_prompt_tokens | {_format_value(tokens.get('average_prompt_tokens'), skipped=tokens.get('status') == 'skipped')} |")
    report_lines.append(f"| average_completion_tokens | {_format_value(tokens.get('average_completion_tokens'), skipped=tokens.get('status') == 'skipped')} |")
    report_lines.append(f"| average_total_tokens | {_format_value(tokens.get('average_total_tokens'), skipped=tokens.get('status') == 'skipped')} |")
    report_lines.append("")
    report_lines.append("## Notes")
    report_lines.append("")
    report_lines.append("- Metrics are only reported when the corresponding production function executes successfully.")
    report_lines.append("- When the runtime or API dependency is missing, the report uses 'Evaluation skipped' instead of a fabricated value.")
    return "\n".join(report_lines)


def write_report(path: Path | str | None = None) -> Path:
    output_path = Path(path or REPORT_PATH)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = generate_report()
    output_path.write_text(content, encoding="utf-8")
    return output_path


def main() -> None:
    output_path = write_report()
    print(output_path)


if __name__ == "__main__":
    main()
