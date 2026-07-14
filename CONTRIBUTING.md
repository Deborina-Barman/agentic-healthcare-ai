# Contributing to SevaCare AI

Thanks for helping improve SevaCare AI. This repository is an educational and research-oriented clinical-intake prototype; contributions must preserve that scope and avoid claims of medical validation.

## Before opening a pull request

1. Create a focused branch from the current default branch.
2. Keep changes scoped to one concern: UI, API, orchestration, retrieval, evaluation, or documentation.
3. Do not add credentials, patient data, or generated evaluation results that cannot be reproduced.
4. Update documentation when behavior, installation, endpoints, or limitations change.

## Local checks

```bash
# Backend/unit checks available in this repository
python -m unittest

# Frontend production build
cd frontend
npm run build
```

Run the evaluation scripts only when their required dependencies and services are configured. The evaluation framework intentionally records skipped runs instead of fabricated metrics; preserve that behavior.

## Pull request guidance

- Explain the problem, implementation, and verification performed.
- Call out changes to prompts, clinical-state logic, triage behavior, or data artifacts explicitly.
- Keep the dashboard clinician-facing, accessible, and non-diagnostic.
- Do not introduce clinical claims, treatment advice, or performance numbers without reproducible evidence.

## Reporting issues

For defects, include the affected entry point, a minimal reproduction, expected versus actual behavior, and relevant non-sensitive logs. Do not include protected health information.
