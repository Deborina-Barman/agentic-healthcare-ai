# SevaCare AI Evaluation Framework

**Navigation:** [Repository overview](../README.md) · [Latest committed report](results/evaluation_report.md)

This directory contains a production-oriented evaluation framework for the existing SevaCare AI modules.

## What is evaluated

- NLICE extraction quality by invoking the real production extraction function where available.
- Retrieval quality by calling the real follow-up retrieval function where available.
- Summary coverage against expected clinical facts through the real summary agent where available.
- Urgency classification through the real urgency classifier where available.
- OCR extraction quality through the OCR pipeline when the required runtime or API dependencies are present.
- Conversation completion behavior through the chat controller when it can be imported and executed.

## Folder layout

- fixtures/: reusable JSON fixture files used as labeled inputs only.
- evaluate_nlice.py: attempts chat_controller.extract_info_node and records skipped status if not available.
- evaluate_retrieval.py: attempts followup_retriever.retrieve_followup_examples and records skipped status if not available.
- evaluate_summary.py: attempts agents.summary_agent.summary_agent and records skipped status if not available.
- evaluate_urgency.py: attempts agents.urgency_classifier_agent.urgency_classifier_agent and records skipped status if not available.
- evaluate_ocr.py: attempts the OCR pipeline and reports skipped status when dependencies or APIs are missing.
- evaluate_conversation.py: attempts chat_controller.ChatController.handle_text and marks skipped if it cannot run.
- evaluate_latency.py: measures latency around the real controller path when available.
- evaluate_tokens.py: reports token metadata only when the production controller exposes it; otherwise it records skipped.
- generate_report.py: writes evaluation/results/evaluation_report.md and marks each section as evaluated or skipped.
- results/: generated artifacts.

## How to run

From the repository root:

```bash
python evaluation/evaluate_nlice.py
python evaluation/evaluate_retrieval.py
python evaluation/evaluate_summary.py
python evaluation/evaluate_urgency.py
python evaluation/evaluate_ocr.py
python evaluation/evaluate_conversation.py
python evaluation/evaluate_latency.py
python evaluation/evaluate_tokens.py
python evaluation/generate_report.py
```

After a run, review [`evaluation/results/evaluation_report.md`](results/evaluation_report.md). Results are runtime-dependent; do not compare or publish values without recording the environment and dependencies used.

## Execution semantics

- The evaluators first attempt to use the production path.
- Fixtures remain labeled inputs for the evaluation cases.
- If the required dependency, model artifact, or API is unavailable, the evaluator returns status: skipped and a skipped_reason rather than fabricating a metric.
- The generated markdown report distinguishes evaluated runs from skipped runs and lists the production functions that were attempted.

## Dataset format

Each JSON file in fixtures is a list of cases. Each case contains an id and case-specific expected fields.

## Metrics explained

- Accuracy: proportion of correct predictions.
- Precision: how many predicted positives are correct.
- Recall: how many true positives are recovered.
- F1: harmonic mean of precision and recall.
- Precision@1 / Precision@3: ratio of relevant results in the top-k positions.
- Recall@3: the fraction of expected relevant examples retrieved within the top 3.
- Hit@3: whether any expected example appears in the top 3.
- MRR: mean reciprocal rank of the first relevant result.

## Notes

- The evaluators only report metrics that are produced from a real evaluation run.
- When a dependency or external API is unavailable, the framework reports 'Evaluation skipped' instead of fabricating an estimate.
- The generated markdown report is written to evaluation/results/evaluation_report.md.
