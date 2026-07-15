from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CASES_PATH = BASE_DIR / "fixtures" / "conversation_cases.json"


def load_conversation_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path or CASES_PATH)
    with cases_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _import_controller() -> tuple[Any | None, str | None]:
    try:
        module = importlib.import_module("chat_controller")
    except Exception as exc:
        return None, f"Could not import chat_controller: {exc}"
    try:
        return getattr(module, "ChatController"), None
    except AttributeError as exc:
        return None, f"chat_controller.ChatController not found: {exc}"


def evaluate_conversation(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_conversation_cases(path)
    controller_cls, import_error = _import_controller()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["chat_controller.ChatController.handle_text"],
            "case_count": len(cases),
            "completed_cases": 0,
            "completion_rate": None,
            "details": [],
        }

    completed = 0
    details = []
    for case in cases:
        input_text = case.get("input_text") or case.get("patient_complaint") or ""
        try:
            controller = controller_cls()
            response = controller.handle_text(input_text)
            workflow_completed = bool(response.get("summary") or response.get("message"))
            summary_generated = bool(response.get("summary"))
            dashboard_updated = bool(response.get("recommendations"))
            completed += 1 if workflow_completed and summary_generated and dashboard_updated else 0
            details.append({"id": case.get("id"), "workflow_completed": workflow_completed, "summary_generated": summary_generated, "dashboard_updated": dashboard_updated, "status": "evaluated"})
        except Exception as exc:
            details.append({"id": case.get("id"), "workflow_completed": False, "summary_generated": False, "dashboard_updated": False, "status": "skipped", "skipped_reason": str(exc)})
    completion_rate = (completed / len(cases)) if cases else None
    return {
        "status": "evaluated" if details else "skipped",
        "production_functions_called": ["chat_controller.ChatController.handle_text"],
        "case_count": len(cases),
        "completed_cases": completed,
        "completion_rate": completion_rate,
        "details": details,
    }


def main() -> None:
    print(json.dumps(evaluate_conversation(), indent=2))


if __name__ == "__main__":
    main()
