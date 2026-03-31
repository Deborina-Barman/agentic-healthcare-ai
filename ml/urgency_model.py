from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import random

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "model.pkl"
ENCODERS_PATH = BASE_DIR / "encoders.pkl"
FEATURE_COLUMNS = ["nature", "location", "intensity", "chronology", "excitation"]
TARGET_COLUMN = "urgency"


def determine_urgency(record: Dict[str, object]) -> str:
    """Apply simple clinical-style rules to label synthetic NLICE rows."""
    intensity = int(record["intensity"])
    nature = str(record["nature"])
    location = str(record["location"])
    chronology = str(record["chronology"])
    excitation = str(record["excitation"])

    # The dataset does not include a dedicated "breathing difficulty" feature,
    # so sudden severe chest symptoms are used as a proxy emergency pattern.
    if location == "chest" and intensity >= 9 and chronology == "sudden":
        return "EMERGENCY"

    if intensity >= 9:
        return "HIGH"

    if location == "chest" and intensity >= 7:
        return "HIGH"

    if intensity <= 3 and chronology in {"gradual", "days"} and excitation in {"rest", "none"}:
        return "LOW"

    if nature == "burning" and location == "abdomen" and intensity <= 4:
        return "LOW"

    if intensity >= 6 or chronology == "hours" or excitation == "movement":
        return "MODERATE"

    return "LOW"


def generate_synthetic_dataset(num_rows: int = 100, seed: int = 42) -> pd.DataFrame:
    """
    Create a small synthetic dataset when real clinical labels are unavailable.
    Synthetic data helps us prototype the training and prediction pipeline safely.
    """
    random.seed(seed)

    natures = ["sharp", "dull", "burning", "cramping"]
    locations = ["chest", "abdomen", "head", "back"]
    chronologies = ["sudden", "gradual", "hours", "days"]
    excitations = ["movement", "rest", "none"]

    rows = []
    for _ in range(num_rows):
        record = {
            # NLICE gives the model structured symptom context:
            # what it feels like, where it is, how bad it is, when it started,
            # and what triggers or relieves it.
            "nature": random.choice(natures),
            "location": random.choice(locations),
            "intensity": random.randint(1, 10),
            "chronology": random.choice(chronologies),
            "excitation": random.choice(excitations),
        }
        record["urgency"] = determine_urgency(record)
        rows.append(record)

    emergency_examples = [
        {
            "nature": "sharp",
            "location": "chest",
            "intensity": 10,
            "chronology": "sudden",
            "excitation": "movement",
            "urgency": "EMERGENCY",
        },
        {
            "nature": "sharp",
            "location": "chest",
            "intensity": 9,
            "chronology": "sudden",
            "excitation": "rest",
            "urgency": "EMERGENCY",
        },
    ]
    rows.extend(emergency_examples)

    return pd.DataFrame(rows)


def preprocess_data(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, Dict[str, LabelEncoder]]:
    """Encode categorical columns and split the features from the target."""
    processed_df = df.copy()
    encoders: Dict[str, LabelEncoder] = {}

    categorical_columns = ["nature", "location", "chronology", "excitation", "urgency"]
    for column in categorical_columns:
        encoder = LabelEncoder()
        processed_df[column] = encoder.fit_transform(processed_df[column])
        encoders[column] = encoder

    X = processed_df[FEATURE_COLUMNS]
    y = processed_df[TARGET_COLUMN]
    return X, y, encoders


def train_and_save_model(num_rows: int = 100) -> Tuple[RandomForestClassifier, Dict[str, LabelEncoder], float]:
    """Train the urgency classifier, print accuracy, and persist artifacts."""
    df = generate_synthetic_dataset(num_rows=num_rows)
    X, y, encoders = preprocess_data(df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=200, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Model accuracy: {accuracy:.2f}")

    joblib.dump(model, MODEL_PATH)
    joblib.dump(encoders, ENCODERS_PATH)

    return model, encoders, accuracy


def load_artifacts() -> Tuple[RandomForestClassifier, Dict[str, LabelEncoder]]:
    """Load saved model artifacts, training them if they do not exist yet."""
    if not MODEL_PATH.exists() or not ENCODERS_PATH.exists():
        model, encoders, _ = train_and_save_model()
        return model, encoders

    model = joblib.load(MODEL_PATH)
    encoders = joblib.load(ENCODERS_PATH)
    return model, encoders


def predict_urgency(input_dict: Dict[str, object]) -> Dict[str, str]:
    """Predict an urgency label from NLICE-style input features."""
    model, encoders = load_artifacts()

    input_frame = pd.DataFrame([input_dict], columns=FEATURE_COLUMNS)
    encoded_frame = input_frame.copy()

    for column in ["nature", "location", "chronology", "excitation"]:
        encoder = encoders[column]
        value = str(encoded_frame.at[0, column])
        if value not in encoder.classes_:
            allowed = ", ".join(encoder.classes_)
            raise ValueError(f"Unsupported value '{value}' for '{column}'. Allowed values: {allowed}")
        encoded_frame[column] = encoder.transform(encoded_frame[column])

    encoded_frame["intensity"] = encoded_frame["intensity"].astype(int)
    prediction = model.predict(encoded_frame)[0]
    urgency = encoders["urgency"].inverse_transform([prediction])[0]
    return {"urgency": urgency}


def main() -> None:
    train_and_save_model()

    sample_input = {
        "nature": "sharp",
        "location": "chest",
        "intensity": 9,
        "chronology": "sudden",
        "excitation": "movement",
    }
    prediction = predict_urgency(sample_input)
    print("Sample prediction:", prediction)


if __name__ == "__main__":
    main()
