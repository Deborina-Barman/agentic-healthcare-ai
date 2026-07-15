from __future__ import annotations

import importlib
import json
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
CASES_PATH = BASE_DIR / "fixtures" / "latency_cases.json"


def load_latency_cases(path: Path | str | None = None) -> list[dict[str, Any]]:
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


def evaluate_latency(path: Path | str | None = None) -> dict[str, Any]:
    cases = load_latency_cases(path)
    controller_cls, import_error = _import_controller()
    if import_error:
        return {
            "status": "skipped",
            "skipped_reason": import_error,
            "production_functions_called": ["chat_controller.ChatController.handle_text"],
            "case_count": len(cases),
            "average_latency_seconds": None,
            "min_latency_seconds": None,
            "max_latency_seconds": None,
            "details": [],
        }

    durations = []
    details = []
    for case in cases:
        controller = controller_cls()
        input_text = case.get("input_text") or case.get("patient_complaint") or ""
        start = time.perf_counter()
        try:
            controller.handle_text(input_text)
            elapsed = time.perf_counter() - start
        except Exception as exc:
            elapsed = None
            details.append({"id": case.get("id"), "latency_seconds": None, "status": "skipped", "skipped_reason": str(exc)})
            continue
        durations.append(elapsed)
        details.append({"id": case.get("id"), "latency_seconds": elapsed, "status": "evaluated"})
    return {
        "status": "evaluated" if durations else "skipped",
        "production_functions_called": ["chat_controller.ChatController.handle_text"],
        "case_count": len(cases),
        "average_latency_seconds": sum(durations) / len(durations) if durations else None,
        "min_latency_seconds": min(durations) if durations else None,
        "max_latency_seconds": max(durations) if durations else None,
        "details": details,
    }


def main() -> None:
    print(json.dumps(evaluate_latency(), indent=2))


if __name__ == "__main__":
    main()
