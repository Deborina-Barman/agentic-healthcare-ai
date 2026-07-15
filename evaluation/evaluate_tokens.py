from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CASES_PATH = BASE_DIR / "fixtures" / "latency_cases.json"


def load_token_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
    cases_path = Path(path or CASES_PATH)
    if not cases_path.exists():
        cases_path = BASE_DIR / "test_cases" / "latency_cases.json"
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


def evaluate_tokens(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_token_cases(path)
    controller_cls, import_error = _import_controller()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["chat_controller.ChatController.handle_text"],
            "case_count": len(cases),
            "average_prompt_tokens": None,
            "average_completion_tokens": None,
            "average_total_tokens": None,
            "details": [],
        }

    details = []
    for case in cases:
        input_text = case.get("input_text") or case.get("patient_complaint") or ""
        try:
            controller = controller_cls()
            controller.handle_text(input_text)
        except Exception as exc:
            details.append({"id": case.get("id"), "status": "skipped", "skipped_reason": str(exc)})
            continue
        details.append({"id": case.get("id"), "status": "skipped", "skipped_reason": "No token accounting metadata is exposed by the production controller"})
    return {
        "status": "skipped",
        "skipped_reason": "No token accounting metadata is exposed by the production controller",
        "production_functions_called": ["chat_controller.ChatController.handle_text"],
        "case_count": len(cases),
        "average_prompt_tokens": None,
        "average_completion_tokens": None,
        "average_total_tokens": None,
        "details": details,
    }


def main() -> None:
    print(json.dumps(evaluate_tokens(), indent=2))


if __name__ == "__main__":
    main()
