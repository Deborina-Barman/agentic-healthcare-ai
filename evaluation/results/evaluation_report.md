# SevaCare AI Evaluation Report

## Overview

- This report attempts to exercise the real SevaCare production pipeline whenever the required runtime and API dependencies are available.
- Fixture JSON files are treated as labeled inputs only; they are not used as fabricated metrics.
- NLICE evaluation cases: 10
- Retrieval evaluation cases: 10
- Summary evaluation cases: 2
- OCR evaluation cases: 10
- Conversation evaluation cases: 10

## NLICE Metrics

- Status: evaluated
- Production functions called: chat_controller.extract_info_node

| Metric | Value |
| --- | --- |
| accuracy | 0.06666666666666667 |
| precision | 0.0026666666666666666 |
| recall | 0.04 |
| f1 | 0.005 |

## Retrieval Metrics

- Status: evaluated
- Production functions called: followup_retriever.retrieve_followup_examples

| Metric | Value |
| --- | --- |
| precision_at_1 | 0.3 |
| precision_at_3 | 0.36666666666666664 |
| recall_at_3 | 0.36666666666666664 |
| hit_at_3 | 0.6 |
| mrr | 0.3 |

## Summary Metrics

- Status: evaluated
- Production functions called: agents.summary_agent.summary_agent

| Metric | Value |
| --- | --- |
| complaint_captured | 1.0 |
| duration_captured | 0.0 |
| medication_captured | 1.0 |
| medication_response_captured | 0.0 |
| negative_findings_correct | 1.0 |
| hallucinated_findings | 0.0 |
| overall_factual_correctness | 1.0 |

## Urgency Metrics

- Status: evaluated
- Production functions called: agents.urgency_classifier_agent.urgency_classifier_agent

| Metric | Value |
| --- | --- |
| accuracy | 0.9 |
| precision | 0.6666666666666666 |
| recall | 0.75 |
| f1 | 0.7 |

## OCR Metrics

- Status: evaluated
- Production functions called: agents.reader_agent.vision_reader_agent, services.gemini_vision_service.read_prescription_with_gemini

| Metric | Value |
| --- | --- |
| extraction_accuracy | unavailable |
| missing_fields | 0 |
| incorrect_values | 0 |

## Conversation Completion

- Status: evaluated
- Production functions called: chat_controller.ChatController.handle_text

- Completion rate: 0.0
- Completed cases: 0 / 10

## Latency Statistics

- Status: evaluated
- Production functions called: chat_controller.ChatController.handle_text

| Metric | Value |
| --- | --- |
| average_latency_seconds | 0.7610718500218354 |
| min_latency_seconds | 0.08727680006995797 |
| max_latency_seconds | 1.4348668999737129 |

## Token Usage

- Status: skipped
- Production functions called: chat_controller.ChatController.handle_text
- Skipped reason: No token accounting metadata is exposed by the production controller

| Metric | Value |
| --- | --- |
| average_prompt_tokens | Evaluation skipped |
| average_completion_tokens | Evaluation skipped |
| average_total_tokens | Evaluation skipped |

## Notes

- Metrics are only reported when the corresponding production function executes successfully.
- When the runtime or API dependency is missing, the report uses 'Evaluation skipped' instead of a fabricated value.