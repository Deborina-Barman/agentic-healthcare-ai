from __future__ import annotations

from pathlib import Path
import re
from typing import Dict

import joblib


BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "ml" / "model.pkl"
ENCODERS_PATH = BASE_DIR / "ml" / "encoders.pkl"
FEATURE_COLUMNS = ["nature", "location", "intensity", "chronology", "excitation"]
ALLOWED_NATURE_VALUES = ["burning", "cramping", "dull", "sharp", "unknown"]


def load_model_artifacts():
    """Load the trained urgency model and the label encoders."""
    if not MODEL_PATH.exists() or not ENCODERS_PATH.exists():
        raise FileNotFoundError(
            "Missing ML artifacts. Train the model first by running ml/urgency_model.py."
        )

    model = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODERS_PATH)
    return model, encoders


def _extract_nlice_features(state: Dict[str, object]) -> Dict[str, object]:
    """
    Pull NLICE-style features from the top-level state or from patient_answers.
    This keeps the agent flexible while the rest of the app is still evolving.
    """
    patient_answers = state.get("patient_answers") or {}
    nlice = state.get("nlice") or {}

    features = {}
    for feature in FEATURE_COLUMNS:
        if feature in state:
            features[feature] = state.get(feature)
        elif feature in nlice:
            features[feature] = nlice.get(feature)
        else:
            features[feature] = patient_answers.get(feature)

    nature = str(features.get("nature", "")).strip().lower()
    features["nature"] = nature if nature in ALLOWED_NATURE_VALUES else "unknown"

    for field in ("location", "chronology", "excitation"):
        value = str(features.get(field, "")).strip()
        features[field] = value or "unknown"

    intensity_value = features.get("intensity")
    if isinstance(intensity_value, (int, float)):
        features["intensity"] = int(intensity_value)
    else:
        intensity_text = str(intensity_value).strip() if intensity_value is not None else ""
        match = re.search(r"\d+", intensity_text)
        features["intensity"] = int(match.group()) if match else 5

    return features


def _encode_features(features: Dict[str, object], encoders) -> list[list[int]]:
    """Encode saved NLICE categories in the same way the training pipeline did."""
    encoded_row = []

    for column in FEATURE_COLUMNS:
        value = features[column]

        if column == "intensity":
            encoded_row.append(int(value))
            continue

        encoder = encoders[column]
        value = str(value)
        if value not in encoder.classes_:
            fallback = "unknown" if "unknown" in encoder.classes_ else str(encoder.classes_[0])
            value = fallback

        encoded_value = int(encoder.transform([value])[0])
        encoded_row.append(encoded_value)

    return [encoded_row]


def urgency_classifier_agent(state: Dict[str, object]) -> Dict[str, str]:
    """
    Predict urgency from NLICE features using the trained ML model.
    Falls back to HIGH for very severe intensity, even if the model predicts lower.
    """
    model, encoders = load_model_artifacts()
    features = _extract_nlice_features(state)
    encoded_features = _encode_features(features, encoders)

    prediction = model.predict(encoded_features)[0]
    predicted_label = str(encoders["urgency"].inverse_transform([prediction])[0])

    if features["intensity"] >= 9 and predicted_label not in {"HIGH", "EMERGENCY"}:
        predicted_label = "HIGH"

    return {
        "urgency_level": predicted_label,
        "reason": "Based on intensity and symptom pattern",
    }


def main() -> None:
    sample_state = {
        "nature": "sharp",
        "location": "chest",
        "intensity": 9,
        "chronology": "sudden",
        "excitation": "movement",
    }
    result = urgency_classifier_agent(sample_state)
    print(result)


if __name__ == "__main__":
    main()
