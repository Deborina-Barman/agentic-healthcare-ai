"""
Advanced evaluation framework for OCR and information extraction pipeline.

Enhancements:
1. Comprehensive field-type normalization (gender, age, duration, medicine, diagnosis)
2. Fuzzy matching for free-text fields (90% similarity threshold)
3. Intelligent OCR metrics (normalize whitespace, ignore blank lines)
4. Medicine list element-by-element comparison
5. Enhanced error reporting with similarity scores and classification
6. Recomputed metrics after normalization with confusion statistics
7. Improved markdown report with evaluation observations

Evaluates:
1. OCR Quality (CER, WER with whitespace normalization)
2. Information Extraction Quality (semantic + fuzzy matching)
3. Pipeline Latencies (excluding warm-up)

Automatically processes all images in the evaluation/images directory.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any
from collections import defaultdict

import jiwer

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("RapidFuzz not installed. Fuzzy matching disabled. Run: pip install rapidfuzz")

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import production services
from services.gemini_information_extractor import (
    extract_clinical_information,
    GeminiInformationExtractionError,
)
from services.paddle_ocr_service import read_document_with_paddle, PaddleOCRError

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

IMAGES_DIR = BASE_DIR / "images"
GROUND_TRUTH_DIR = BASE_DIR / "ground_truth"
EXPECTED_JSON_DIR = BASE_DIR / "expected_json"
RESULTS_DIR = BASE_DIR / "results"

# Field types that benefit from fuzzy matching
FREE_TEXT_FIELDS = {
    "patient_name", "doctor", "hospital", "diagnosis", "clinical_notes",
    "patient", "patient_full_name", "physician", "practitioner", "notes",
    "chief_complaint", "presenting_complaint", "symptoms"
}
FUZZY_MATCH_THRESHOLD = 0.90  # 90% similarity


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for OCR evaluation.
    
    - Lowercase conversion
    - Unicode normalization
    - Collapse multiple spaces
    - Remove repeated newlines
    - Convert tabs to spaces
    - Trim whitespace
    """
    if not isinstance(text, str):
        return ""
    
    # Unicode normalization (NFD) to remove accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    
    # Lowercase
    text = text.lower()
    
    # Convert tabs to spaces
    text = text.replace("\t", " ")
    
    # Collapse multiple spaces into single
    text = re.sub(r" +", " ", text)
    
    # Remove repeated newlines (keep single newlines)
    text = re.sub(r"\n\n+", "\n", text)
    
    # Trim whitespace
    text = text.strip()
    
    return text


def normalize_whitespace_ocr(text: str) -> str:
    """
    Normalize whitespace for OCR comparison.
    - Collapse multiple spaces
    - Remove trailing spaces from lines
    - Remove blank lines
    - Preserve line structure for readability
    """
    if not isinstance(text, str):
        return ""
    
    lines = text.split('\n')
    # Remove trailing spaces and empty lines
    lines = [line.rstrip() for line in lines if line.strip()]
    text = '\n'.join(lines)
    
    return text.strip()


def normalize_gender(text: str) -> str:
    """Normalize gender values."""
    text = text.lower().strip()
    
    # Male variations
    if text in ("m", "male", "male.", "boy", "man", "masculine"):
        return "male"
    
    # Female variations
    if text in ("f", "female", "female.", "girl", "woman", "feminine"):
        return "female"
    
    return text


def normalize_age(text: str) -> str:
    """
    Normalize age values.
    Extract numeric age only.
    
    Examples:
    - "73" → "73"
    - "73 years" → "73"
    - "73 yrs" → "73"
    - "73 Yrs" → "73"
    """
    if not isinstance(text, str):
        return ""
    
    text = text.lower().strip()
    
    # Extract numeric value
    match = re.search(r'\d+', text)
    if match:
        return match.group(0)
    
    return text


def normalize_duration(text: str) -> str:
    """
    Normalize duration values.
    
    Examples:
    - "3 day" → "3 days"
    - "3 days" → "3 days"
    - "3day" → "3 days"
    - "03 days" → "3 days"
    """
    if not isinstance(text, str):
        return ""
    
    text = text.lower().strip()
    
    # Remove leading zeros from numbers
    text = re.sub(r'\b0+(\d+)', r'\1', text)
    
    # Normalize "days"
    text = re.sub(r'day(?!s)', 'days', text)
    text = re.sub(r'\bd\b', 'days', text)
    
    # Normalize "weeks"
    text = re.sub(r'week(?!s)', 'weeks', text)
    text = re.sub(r'\bw\b', 'weeks', text)
    
    # Normalize "months"
    text = re.sub(r'month(?!s)', 'months', text)
    
    # Normalize "hours"
    text = re.sub(r'hour(?!s)', 'hours', text)
    text = re.sub(r'\bh\b', 'hours', text)
    
    # Collapse spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


def normalize_medicine_name(text: str) -> str:
    """
    Normalize medicine names.
    
    Examples:
    - "Augmentin." → "augmentin"
    - "Augmentin-" → "augmentin"
    - "AUGMENTIN" → "augmentin"
    - "Pan-D" → "pan d"
    - "Pan.D" → "pan d"
    """
    if not isinstance(text, str):
        return ""
    
    text = text.lower().strip()
    
    # Remove trailing punctuation
    text = re.sub(r'[\.\-\s]+$', '', text)
    
    # Replace hyphens and periods with spaces (but not leading/trailing)
    text = re.sub(r'[-\.]', ' ', text)
    
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


def normalize_diagnosis(text: str) -> str:
    """
    Normalize diagnosis/status values.
    Handle medical abbreviations.
    
    Examples:
    - "COVID positive" → "covid positive"
    - "COVID +ve" → "covid positive"
    - "COVID+" → "covid positive"
    - "+ve" → "positive"
    - "-ve" → "negative"
    """
    if not isinstance(text, str):
        return ""
    
    text = text.lower().strip()
    
    # Normalize positive/negative markers
    text = re.sub(r'\+ve|\+|positive', 'positive', text)
    text = re.sub(r'-ve|-(?!negative)|negative', 'negative', text)
    
    # Remove extra spaces around "case"
    text = re.sub(r'\s+case\s*$', '', text)
    
    # Collapse spaces
    text = re.sub(r'\s+', ' ', text)
    
    return text


def get_field_type(field_name: str) -> str:
    """Determine field type for appropriate normalization."""
    field_lower = field_name.lower()
    
    if "gender" in field_lower or "sex" in field_lower:
        return "gender"
    elif "age" in field_lower:
        return "age"
    elif "duration" in field_lower or "period" in field_lower:
        return "duration"
    elif "medicine" in field_lower or "drug" in field_lower or "medication" in field_lower:
        return "medicine"
    elif "diagnosis" in field_lower or "status" in field_lower or "condition" in field_lower:
        return "diagnosis"
    elif field_name in FREE_TEXT_FIELDS:
        return "free_text"
    else:
        return "generic"


def normalize_field_value(value: Any, field_type: str | None = None, field_name: str = "") -> str:
    """
    Normalize field values with type-specific rules.
    
    Args:
        value: Value to normalize
        field_type: Explicit field type (gender, age, medicine, etc.)
        field_name: Field name (used to infer type if not provided)
    """
    if value is None or value == "":
        return ""
    
    text = str(value).strip()
    
    # Infer field type if not provided
    if not field_type:
        field_type = get_field_type(field_name)
    
    # Apply type-specific normalization
    if field_type == "gender":
        return normalize_gender(text)
    elif field_type == "age":
        return normalize_age(text)
    elif field_type == "duration":
        return normalize_duration(text)
    elif field_type == "medicine":
        return normalize_medicine_name(text)
    elif field_type == "diagnosis":
        return normalize_diagnosis(text)
    else:
        # Generic normalization
        text = text.lower().strip()
        text = re.sub(r'[\.\-\s]+$', '', text)  # Remove trailing punctuation
        text = re.sub(r'\s+', ' ', text)  # Collapse spaces
        return text


# ============================================================================
# FUZZY MATCHING FUNCTIONS
# ============================================================================

def fuzzy_compare(expected: str, predicted: str, threshold: float = FUZZY_MATCH_THRESHOLD) -> tuple[bool, float]:
    """
    Compare strings using fuzzy matching.
    
    Returns: (is_match, similarity_score)
    """
    if not RAPIDFUZZ_AVAILABLE:
        return expected == predicted, 1.0 if expected == predicted else 0.0
    
    if not expected or not predicted:
        return expected == predicted, 1.0 if expected == predicted else 0.0
    
    # Use token_set_ratio for better matching with different word orders
    similarity = fuzz.token_set_ratio(expected, predicted) / 100.0
    
    is_match = similarity >= threshold
    return is_match, similarity


# ============================================================================
# OCR EVALUATION FUNCTIONS
# ============================================================================

def calculate_cer_wer(reference: str, hypothesis: str) -> dict[str, float]:
    """
    Calculate Character Error Rate (CER) and Word Error Rate (WER).
    
    Normalizes whitespace before comparison but preserves overall text structure.
    Returns values in range [0, 1] where 0 = perfect match.
    """
    # Normalize whitespace (remove extra spaces and blank lines)
    reference = normalize_whitespace_ocr(reference)
    hypothesis = normalize_whitespace_ocr(hypothesis)
    
    # Also normalize text for better comparison
    reference = normalize_text(reference)
    hypothesis = normalize_text(hypothesis)
    
    try:
        cer = jiwer.cer(reference, hypothesis)
        wer = jiwer.wer(reference, hypothesis)
        return {"cer": float(cer), "wer": float(wer)}
    except Exception as e:
        logger.warning(f"Error calculating CER/WER: {e}")
        return {"cer": 1.0, "wer": 1.0}


# ============================================================================
# JSON COMPARISON FUNCTIONS
# ============================================================================

def compare_field_value(
    expected: str, 
    predicted: str, 
    field_name: str = "",
    field_type: str | None = None
) -> tuple[bool, dict[str, Any]]:
    """
    Compare two field values semantically.
    
    Returns: (is_match, error_info)
    where error_info contains: {"similarity", "status", "normalized_expected", "normalized_predicted"}
    """
    expected = str(expected).strip()
    predicted = str(predicted).strip()
    
    # Normalize both values
    norm_expected = normalize_field_value(expected, field_type, field_name)
    norm_predicted = normalize_field_value(predicted, field_type, field_name)
    
    error_info = {
        "normalized_expected": norm_expected,
        "normalized_predicted": norm_predicted,
        "similarity": 0.0,
        "status": "unknown"
    }
    
    # Exact match after normalization
    if norm_expected == norm_predicted:
        error_info["similarity"] = 1.0
        error_info["status"] = "normalized_match"
        return True, error_info
    
    # Fuzzy matching for free-text fields
    if field_name in FREE_TEXT_FIELDS or "free_text" in str(field_type):
        is_match, similarity = fuzzy_compare(norm_expected, norm_predicted, FUZZY_MATCH_THRESHOLD)
        error_info["similarity"] = similarity
        
        if is_match:
            error_info["status"] = "fuzzy_match" if similarity < 1.0 else "normalized_match"
            return True, error_info
        else:
            error_info["status"] = "genuinely_different"
            return False, error_info
    
    # For non-free-text fields, fuzzy matching at 95%+ similarity
    is_match, similarity = fuzzy_compare(norm_expected, norm_predicted, 0.95)
    error_info["similarity"] = similarity
    
    if is_match:
        # Minor spelling variations
        error_info["status"] = "ocr_spelling_variation" if similarity < 1.0 else "normalized_match"
        return True, error_info
    
    error_info["status"] = "value_mismatch"
    return False, error_info


def compare_medicine_lists(
    expected_list: list[Any], 
    predicted_list: list[Any]
) -> tuple[int, int, int, list[dict]]:
    """
    Compare medicine lists element by element.
    
    Returns: (matched, missing, incorrect, error_details)
    """
    matched = 0
    missing = 0
    incorrect = 0
    error_details = []
    
    if not isinstance(expected_list, list):
        expected_list = [expected_list] if expected_list else []
    if not isinstance(predicted_list, list):
        predicted_list = [predicted_list] if predicted_list else []
    
    # Track which medicines were matched
    matched_indices = set()
    
    # Try to match each expected medicine
    for exp_med in expected_list:
        exp_name = str(exp_med.get("name", "") if isinstance(exp_med, dict) else exp_med).strip()
        
        if not exp_name:
            continue
        
        exp_name_norm = normalize_medicine_name(exp_name)
        found_match = False
        best_similarity = 0.0
        best_idx = -1
        
        for pred_idx, pred_med in enumerate(predicted_list):
            if pred_idx in matched_indices:
                continue
            
            pred_name = str(pred_med.get("name", "") if isinstance(pred_med, dict) else pred_med).strip()
            pred_name_norm = normalize_medicine_name(pred_name)
            
            if exp_name_norm == pred_name_norm:
                found_match = True
                best_idx = pred_idx
                best_similarity = 1.0
                break
            
            # Fuzzy match
            is_match, similarity = fuzzy_compare(exp_name_norm, pred_name_norm, 0.85)
            if is_match and similarity > best_similarity:
                found_match = True
                best_idx = pred_idx
                best_similarity = similarity
        
        if found_match:
            matched_indices.add(best_idx)
            matched += 1
        else:
            missing += 1
            error_details.append({
                "medicine": exp_name,
                "error_type": "missing",
                "status": "not_extracted"
            })
    
    # Count extra medicines as false positives
    for idx, pred_med in enumerate(predicted_list):
        if idx not in matched_indices:
            incorrect += 1
            pred_name = str(pred_med.get("name", "") if isinstance(pred_med, dict) else pred_med).strip()
            error_details.append({
                "medicine": pred_name,
                "error_type": "extra",
                "status": "hallucinated"
            })
    
    return matched, missing, incorrect, error_details


def compare_json_semantic(
    expected: dict[str, Any],
    predicted: dict[str, Any],
) -> dict[str, Any]:
    """
    Recursively compare two JSON structures with semantic normalization.
    
    Returns detailed comparison results with error analysis.
    """
    matched_fields = 0
    missing_fields = []
    incorrect_fields = []
    error_analysis = []
    confusion_stats = {
        "matched_after_normalization": 0,
        "matched_by_fuzzy_similarity": 0,
        "actually_incorrect": 0,
        "missing": 0,
    }
    
    def compare_field(key: str, exp_value: Any, pred_value: Any) -> int:
        """
        Compare a single field value.
        Returns: 1 if matched, 0 otherwise
        """
        nonlocal error_analysis
        
        # Missing or empty predicted field
        if pred_value is None or (isinstance(pred_value, (str, list, dict)) and not pred_value):
            missing_fields.append(key)
            confusion_stats["missing"] += 1
            error_analysis.append({
                "field": key,
                "expected": str(exp_value)[:50],
                "predicted": "(missing)",
                "error_type": "missing",
                "status": "field_not_extracted"
            })
            return 0
        
        # List comparison (medicines, diagnoses, etc.)
        if isinstance(exp_value, list) and isinstance(pred_value, list):
            if "medicine" in key.lower() or "drug" in key.lower():
                matched, missing, incorrect, details = compare_medicine_lists(exp_value, pred_value)
                
                for detail in details:
                    error_analysis.append({
                        "field": key,
                        "medicine": detail["medicine"],
                        "error_type": detail["error_type"],
                        "status": detail["status"]
                    })
                
                confusion_stats["missing"] += missing
                confusion_stats["actually_incorrect"] += incorrect
                
                return 1 if incorrect == 0 and missing == 0 else 0
            else:
                # Generic list comparison
                if len(exp_value) == len(pred_value):
                    all_match = True
                    for e, p in zip(exp_value, pred_value):
                        is_match, _ = compare_field_value(str(e), str(p), key)
                        if not is_match:
                            all_match = False
                            break
                    if all_match:
                        confusion_stats["matched_after_normalization"] += 1
                        return 1
        
        # String/numeric comparison
        exp_str = str(exp_value).strip()
        pred_str = str(pred_value).strip()
        
        if not exp_str:
            return 1  # Empty expected field - no penalty
        
        is_match, error_info = compare_field_value(exp_str, pred_str, key)
        
        if is_match:
            if error_info["status"] == "normalized_match":
                confusion_stats["matched_after_normalization"] += 1
            else:
                confusion_stats["matched_by_fuzzy_similarity"] += 1
            return 1
        else:
            confusion_stats["actually_incorrect"] += 1
            incorrect_fields.append({
                "field": key,
                "expected": exp_str[:50],
                "predicted": pred_str[:50],
                "similarity": error_info["similarity"],
                "status": error_info["status"],
            })
            error_analysis.append({
                "field": key,
                "expected": exp_str[:50],
                "predicted": pred_str[:50],
                "similarity": f"{error_info['similarity']:.2%}",
                "error_type": "value_mismatch",
                "status": error_info["status"],
            })
            return 0
    
    # Compare all expected fields
    total_fields = len(expected)
    for key, exp_value in expected.items():
        pred_value = predicted.get(key)
        matches = compare_field(key, exp_value, pred_value)
        matched_fields += matches
    
    return {
        "total_fields": total_fields,
        "matched_fields": matched_fields,
        "missing_fields": missing_fields,
        "incorrect_fields": incorrect_fields,
        "error_analysis": error_analysis,
        "confusion_stats": confusion_stats,
    }


# ============================================================================
# METRICS CALCULATION
# ============================================================================

def calculate_metrics(matched: int, total: int, missing: int, incorrect: int) -> dict[str, float]:
    """
    Calculate Precision, Recall, and F1-score using TP/FP/FN.
    """
    true_positives = matched
    false_positives = incorrect
    false_negatives = missing
    
    # Accuracy
    accuracy = true_positives / total if total > 0 else 0.0
    
    # Precision
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0.0
    )
    
    # Recall
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0.0
    )
    
    # F1-score
    if precision + recall > 0:
        f1_score = 2 * (precision * recall) / (precision + recall)
    else:
        f1_score = 0.0
    
    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1_score": float(f1_score),
    }


# ============================================================================
# FILE LOADING FUNCTIONS
# ============================================================================

def _load_image_bytes(image_path: Path) -> bytes:
    """Load image bytes from file."""
    with open(image_path, "rb") as f:
        return f.read()


def _load_ground_truth(text_path: Path) -> str:
    """Load ground truth OCR text."""
    with open(text_path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_expected_json(json_path: Path) -> dict[str, Any]:
    """Load expected structured output."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================================
# EVALUATION FUNCTIONS
# ============================================================================

def evaluate_single_image(
    image_name: str,
    image_bytes: bytes,
    ground_truth_text: str,
    expected_json: dict[str, Any],
) -> dict[str, Any]:
    """
    Evaluate a single image through the complete pipeline.
    
    Returns per-image evaluation results with detailed analysis.
    """
    result = {
        "image": image_name,
        "status": "failed",
        "ocr": {},
        "information_extraction": {},
        "pipeline": {},
        "errors": [],
    }
    
    # Step 1: OCR with PaddleOCR
    logger.info(f"Running OCR on {image_name}")
    ocr_start = time.time()
    try:
        ocr_text = read_document_with_paddle(image_bytes)
        ocr_latency_ms = (time.time() - ocr_start) * 1000
        
        # Calculate CER and WER with whitespace normalization
        error_metrics = calculate_cer_wer(ground_truth_text, ocr_text)
        
        result["ocr"] = {
            "latency_ms": ocr_latency_ms,
            "cer": error_metrics["cer"],
            "wer": error_metrics["wer"],
            "output_length": len(ocr_text),
            "ground_truth_length": len(ground_truth_text),
        }
    except PaddleOCRError as e:
        result["errors"].append(f"OCR failed: {str(e)}")
        logger.error(f"OCR failed for {image_name}: {e}")
        return result
    
    # Step 2: Information Extraction with Gemini
    logger.info(f"Running information extraction on {image_name}")
    extraction_start = time.time()
    try:
        predicted_json = extract_clinical_information(ocr_text)
        extraction_latency_ms = (time.time() - extraction_start) * 1000
    except GeminiInformationExtractionError as e:
        result["errors"].append(f"Information extraction failed: {str(e)}")
        logger.error(f"Information extraction failed for {image_name}: {e}")
        return result
    
    # Step 3: Compare extracted JSON with expected JSON
    logger.info(f"Comparing JSON outputs for {image_name}")
    json_comparison = compare_json_semantic(expected_json, predicted_json)
    
    # Calculate metrics
    metrics = calculate_metrics(
        matched=json_comparison["matched_fields"],
        total=json_comparison["total_fields"],
        missing=len(json_comparison["missing_fields"]),
        incorrect=len(json_comparison["incorrect_fields"]),
    )
    
    result["information_extraction"] = {
        "latency_ms": extraction_latency_ms,
        "field_accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1_score": metrics["f1_score"],
        "total_fields": json_comparison["total_fields"],
        "matched_fields": json_comparison["matched_fields"],
        "missing_fields": json_comparison["missing_fields"],
        "incorrect_fields": json_comparison["incorrect_fields"],
    }
    
    result["pipeline"] = {
        "total_latency_ms": result["ocr"]["latency_ms"] + extraction_latency_ms,
    }
    
    # Error analysis with confusion statistics
    result["error_analysis"] = json_comparison["error_analysis"]
    result["confusion_stats"] = json_comparison["confusion_stats"]
    
    result["status"] = "success"
    return result


def perform_warmup_ocr():
    """
    Perform a warm-up OCR call to exclude model loading time from averages.
    """
    try:
        logger.info("Performing warm-up OCR call...")
        from PIL import Image
        from io import BytesIO
        
        img = Image.new("RGB", (1, 1), color="white")
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        read_document_with_paddle(img_bytes.getvalue())
        logger.info("Warm-up OCR completed")
    except Exception as e:
        logger.warning(f"Warm-up OCR failed (non-critical): {e}")


def evaluate_pipeline(
    images_dir: Path | str | None = None,
    ground_truth_dir: Path | str | None = None,
    expected_json_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Run complete evaluation pipeline on all images in the dataset.
    
    Automatically discovers all images and their corresponding ground truth
    and expected JSON files.
    """
    images_dir = Path(images_dir or IMAGES_DIR)
    ground_truth_dir = Path(ground_truth_dir or GROUND_TRUTH_DIR)
    expected_json_dir = Path(expected_json_dir or EXPECTED_JSON_DIR)
    
    # Perform warm-up OCR
    perform_warmup_ocr()
    
    # Discover all image files
    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.png"))
    
    if not image_files:
        logger.error(f"No images found in {images_dir}")
        return {
            "status": "failed",
            "error": f"No images found in {images_dir}",
            "images_evaluated": 0,
        }
    
    logger.info(f"Found {len(image_files)} images to evaluate")
    
    per_image_results = []
    ocr_metrics = {"cer_list": [], "wer_list": [], "latency_list": []}
    extraction_metrics = {
        "accuracy_list": [],
        "precision_list": [],
        "recall_list": [],
        "f1_list": [],
    }
    confusion_stats_total = defaultdict(int)
    pipeline_metrics = {"total_latency_list": []}
    all_errors = []
    
    for image_path in image_files:
        # Get corresponding ground truth and expected JSON files
        base_name = image_path.stem
        ground_truth_path = ground_truth_dir / f"{base_name}.txt"
        expected_json_path = expected_json_dir / f"{base_name}.json"
        
        if not ground_truth_path.exists():
            logger.warning(f"Ground truth not found for {base_name}")
            continue
        if not expected_json_path.exists():
            logger.warning(f"Expected JSON not found for {base_name}")
            continue
        
        # Load data
        try:
            image_bytes = _load_image_bytes(image_path)
            ground_truth_text = _load_ground_truth(ground_truth_path)
            expected_json = _load_expected_json(expected_json_path)
        except Exception as e:
            logger.error(f"Failed to load data for {base_name}: {e}")
            continue
        
        # Evaluate single image
        result = evaluate_single_image(
            image_name=base_name,
            image_bytes=image_bytes,
            ground_truth_text=ground_truth_text,
            expected_json=expected_json,
        )
        
        per_image_results.append(result)
        
        # Aggregate metrics
        if result["status"] == "success":
            ocr_metrics["cer_list"].append(result["ocr"]["cer"])
            ocr_metrics["wer_list"].append(result["ocr"]["wer"])
            ocr_metrics["latency_list"].append(result["ocr"]["latency_ms"])
            
            extraction_metrics["accuracy_list"].append(
                result["information_extraction"]["field_accuracy"]
            )
            extraction_metrics["precision_list"].append(
                result["information_extraction"]["precision"]
            )
            extraction_metrics["recall_list"].append(
                result["information_extraction"]["recall"]
            )
            extraction_metrics["f1_list"].append(
                result["information_extraction"]["f1_score"]
            )
            
            pipeline_metrics["total_latency_list"].append(
                result["pipeline"]["total_latency_ms"]
            )
            
            # Aggregate confusion statistics
            if "confusion_stats" in result:
                for key, value in result["confusion_stats"].items():
                    confusion_stats_total[key] += value
            
            # Collect error analysis
            if "error_analysis" in result:
                all_errors.extend([
                    {"image": base_name, **err}
                    for err in result["error_analysis"]
                ])
    
    # Calculate averages
    def safe_average(values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0
    
    final_report = {
        "status": "success" if per_image_results else "failed",
        "images_evaluated": len([r for r in per_image_results if r["status"] == "success"]),
        "ocr": {
            "average_cer": safe_average(ocr_metrics["cer_list"]),
            "average_wer": safe_average(ocr_metrics["wer_list"]),
            "average_latency_ms": safe_average(ocr_metrics["latency_list"]),
        },
        "information_extraction": {
            "field_accuracy": safe_average(extraction_metrics["accuracy_list"]),
            "precision": safe_average(extraction_metrics["precision_list"]),
            "recall": safe_average(extraction_metrics["recall_list"]),
            "f1_score": safe_average(extraction_metrics["f1_list"]),
        },
        "pipeline": {
            "average_total_latency_ms": safe_average(pipeline_metrics["total_latency_list"]),
        },
        "confusion_stats": dict(confusion_stats_total),
        "per_image_results": per_image_results,
        "error_analysis": all_errors,
    }
    
    return final_report


# ============================================================================
# REPORT FORMATTING
# ============================================================================

def format_per_image_report(result: dict[str, Any]) -> str:
    """Format a per-image evaluation result for pretty printing."""
    lines = []
    lines.append("-" * 80)
    lines.append(f"Image: {result['image']}")
    lines.append(f"Status: {result['status'].upper()}")
    
    if result["status"] == "success":
        lines.append("")
        lines.append("OCR Metrics:")
        lines.append(f"  CER: {result['ocr']['cer']:.4f}")
        lines.append(f"  WER: {result['ocr']['wer']:.4f}")
        lines.append(f"  Latency: {result['ocr']['latency_ms']:.2f}ms")
        
        lines.append("")
        lines.append("Information Extraction:")
        lines.append(f"  Field Accuracy: {result['information_extraction']['field_accuracy']:.4f}")
        lines.append(f"  Precision: {result['information_extraction']['precision']:.4f}")
        lines.append(f"  Recall: {result['information_extraction']['recall']:.4f}")
        lines.append(f"  F1-Score: {result['information_extraction']['f1_score']:.4f}")
        lines.append(f"  Latency: {result['information_extraction']['latency_ms']:.2f}ms")
        lines.append(f"  Matched Fields: {result['information_extraction']['matched_fields']}/{result['information_extraction']['total_fields']}")
        
        if result["information_extraction"]["missing_fields"]:
            lines.append(f"  Missing Fields: {', '.join(result['information_extraction']['missing_fields'])}")
        
        if result["information_extraction"]["incorrect_fields"]:
            lines.append(f"  Value Mismatches:")
            for field_error in result["information_extraction"]["incorrect_fields"][:3]:
                similarity = field_error.get('similarity', 0)
                lines.append(f"    - {field_error['field']}: {similarity:.0%} similar")
                lines.append(f"      Expected: '{field_error['expected']}'")
                lines.append(f"      Got: '{field_error['predicted']}'")
            if len(result["information_extraction"]["incorrect_fields"]) > 3:
                lines.append(f"    ... and {len(result['information_extraction']['incorrect_fields']) - 3} more")
    else:
        lines.append("")
        lines.append("Errors:")
        for error in result["errors"]:
            lines.append(f"  - {error}")
    
    lines.append("-" * 80)
    return "\n".join(lines)


def format_final_report(report: dict[str, Any]) -> str:
    """Format the final evaluation report for pretty printing."""
    lines = []
    lines.append("=" * 80)
    lines.append("EVALUATION REPORT")
    lines.append("=" * 80)
    
    lines.append("")
    lines.append("Summary:")
    lines.append(f"  Images Evaluated: {report['images_evaluated']}")
    
    lines.append("")
    lines.append("OCR Evaluation:")
    lines.append(f"  Average CER: {report['ocr']['average_cer']:.4f}")
    lines.append(f"  Average WER: {report['ocr']['average_wer']:.4f}")
    lines.append(f"  Average Latency: {report['ocr']['average_latency_ms']:.2f}ms")
    
    lines.append("")
    lines.append("Information Extraction:")
    lines.append(f"  Average Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
    lines.append(f"  Average Precision: {report['information_extraction']['precision']:.4f}")
    lines.append(f"  Average Recall: {report['information_extraction']['recall']:.4f}")
    lines.append(f"  Average F1-Score: {report['information_extraction']['f1_score']:.4f}")
    
    # Confusion statistics
    stats = report.get("confusion_stats", {})
    if stats:
        lines.append("")
        lines.append("Matching Statistics:")
        lines.append(f"  Exact Match After Normalization: {stats.get('matched_after_normalization', 0)}")
        lines.append(f"  Fuzzy Match (>90% similarity): {stats.get('matched_by_fuzzy_similarity', 0)}")
        lines.append(f"  Actually Incorrect: {stats.get('actually_incorrect', 0)}")
        lines.append(f"  Missing Fields: {stats.get('missing', 0)}")
    
    lines.append("")
    lines.append("Pipeline:")
    lines.append(f"  Average Total Latency: {report['pipeline']['average_total_latency_ms']:.2f}ms")
    
    lines.append("")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def analyze_evaluation_observations(report: dict[str, Any]) -> list[str]:
    """
    Generate observations about pipeline quality based on evaluation results.
    """
    observations = []
    stats = report.get("confusion_stats", {})
    
    # OCR quality observations
    avg_cer = report['ocr']['average_cer']
    avg_wer = report['ocr']['average_wer']
    
    if avg_cer < 0.05:
        observations.append("✓ OCR performance is excellent (CER < 5%)")
    elif avg_cer < 0.10:
        observations.append("✓ OCR performance is good (CER < 10%)")
    elif avg_cer < 0.20:
        observations.append("⚠ OCR performance is fair (CER < 20%)")
    else:
        observations.append("✗ OCR performance needs improvement (CER > 20%)")
    
    # Extraction quality observations
    avg_acc = report['information_extraction']['field_accuracy']
    avg_f1 = report['information_extraction']['f1_score']
    
    if avg_acc > 0.95:
        observations.append("✓ Information extraction is highly accurate (>95% fields correct)")
    elif avg_acc > 0.85:
        observations.append("✓ Information extraction is good (>85% fields correct)")
    elif avg_acc > 0.70:
        observations.append("⚠ Information extraction is acceptable (>70% fields correct)")
    else:
        observations.append("✗ Information extraction needs improvement (<70% fields correct)")
    
    # Normalization impact
    fuzzy_matches = stats.get('matched_by_fuzzy_similarity', 0)
    norm_matches = stats.get('matched_after_normalization', 0)
    if (fuzzy_matches + norm_matches) > 0:
        total_matched = fuzzy_matches + norm_matches
        pct_fuzzy = (fuzzy_matches / total_matched) * 100 if total_matched > 0 else 0
        
        if pct_fuzzy > 20:
            observations.append(f"✓ Semantic normalization recovered {fuzzy_matches} matches ({pct_fuzzy:.0f}%)")
        if norm_matches > 0:
            observations.append(f"✓ Exact match after normalization: {norm_matches} fields")
    
    # Error type analysis
    error_types = defaultdict(int)
    for error in report.get("error_analysis", []):
        error_type = error.get("error_type", "unknown")
        error_types[error_type] += 1
    
    if error_types:
        most_common = max(error_types.items(), key=lambda x: x[1])
        if most_common[0] == "value_mismatch":
            observations.append(f"⚠ Most common issue: Value mismatches (n={most_common[1]})")
        elif most_common[0] == "missing":
            observations.append(f"⚠ Most common issue: Missing fields (n={most_common[1]})")
    
    # OCR vs Gemini assessment
    if avg_cer > avg_acc * 0.5:  # OCR errors significantly impact accuracy
        observations.append("→ OCR quality is the primary constraint on overall pipeline quality")
    else:
        observations.append("→ Gemini extraction is handling OCR errors well")
    
    # Medicine handling
    medicine_errors = [e for e in report.get("error_analysis", []) if e.get("field") and "medicine" in e.get("field", "").lower()]
    if medicine_errors:
        missing_meds = sum(1 for e in medicine_errors if e.get("error_type") == "missing")
        if missing_meds > 0:
            observations.append(f"⚠ {missing_meds} medicines not extracted - review extraction prompt")
    
    return observations


def generate_markdown_report(report: dict[str, Any]) -> str:
    """Generate a comprehensive markdown report."""
    lines = []
    
    lines.append("# SevaCare AI - Pipeline Evaluation Report")
    lines.append("")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    
    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Images Evaluated:** {report['images_evaluated']}")
    lines.append("")
    
    # OCR Evaluation
    lines.append("## OCR Quality")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Average CER | {report['ocr']['average_cer']:.4f} |")
    lines.append(f"| Average WER | {report['ocr']['average_wer']:.4f} |")
    lines.append(f"| Average Latency (ms) | {report['ocr']['average_latency_ms']:.2f} |")
    lines.append("")
    
    # Information Extraction
    lines.append("## Information Extraction Quality")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Field Accuracy | {report['information_extraction']['field_accuracy']:.4f} |")
    lines.append(f"| Precision | {report['information_extraction']['precision']:.4f} |")
    lines.append(f"| Recall | {report['information_extraction']['recall']:.4f} |")
    lines.append(f"| F1-Score | {report['information_extraction']['f1_score']:.4f} |")
    lines.append(f"| Average Latency (ms) | {report['pipeline']['average_total_latency_ms']:.2f} |")
    lines.append("")
    
    # Matching Statistics
    stats = report.get("confusion_stats", {})
    if stats:
        lines.append("## Matching Analysis")
        lines.append("")
        lines.append("| Category | Count |")
        lines.append("|----------|-------|")
        lines.append(f"| Exact Match After Normalization | {stats.get('matched_after_normalization', 0)} |")
        lines.append(f"| Fuzzy Match (≥90% similarity) | {stats.get('matched_by_fuzzy_similarity', 0)} |")
        lines.append(f"| Value Mismatches | {stats.get('actually_incorrect', 0)} |")
        lines.append(f"| Missing Fields | {stats.get('missing', 0)} |")
        lines.append("")
    
    # Per-image results
    lines.append("## Per-Image Results")
    lines.append("")
    lines.append("| Image | CER | WER | Accuracy | F1-Score |")
    lines.append("|-------|-----|-----|----------|----------|")
    for result in report["per_image_results"]:
        if result["status"] == "success":
            lines.append(
                f"| {result['image']} | "
                f"{result['ocr']['cer']:.4f} | "
                f"{result['ocr']['wer']:.4f} | "
                f"{result['information_extraction']['field_accuracy']:.4f} | "
                f"{result['information_extraction']['f1_score']:.4f} |"
            )
    lines.append("")
    
    # Evaluation Observations
    observations = analyze_evaluation_observations(report)
    if observations:
        lines.append("## Evaluation Observations")
        lines.append("")
        for obs in observations:
            lines.append(f"- {obs}")
        lines.append("")
    
    # Error Analysis
    if report.get("error_analysis"):
        lines.append("## Error Analysis")
        lines.append("")
        
        # Group errors by image
        errors_by_image = {}
        for error in report["error_analysis"]:
            image = error.get("image", "unknown")
            if image not in errors_by_image:
                errors_by_image[image] = []
            errors_by_image[image].append(error)
        
        for image, errors in sorted(errors_by_image.items()):
            lines.append(f"### {image}")
            lines.append("")
            
            # Organize errors by type
            by_type = defaultdict(list)
            for error in errors:
                error_type = error.get("error_type", "unknown")
                by_type[error_type].append(error)
            
            for error_type, type_errors in sorted(by_type.items()):
                lines.append(f"**{error_type.replace('_', ' ').title()}** ({len(type_errors)})")
                lines.append("")
                
                for error in type_errors[:3]:
                    field = error.get("field", "unknown")
                    status = error.get("status", "")
                    
                    if error_type == "value_mismatch":
                        similarity = error.get("similarity", "N/A")
                        expected = error.get("expected", "")
                        predicted = error.get("predicted", "")
                        lines.append(f"- **{field}** ({similarity}% match)")
                        lines.append(f"  - Expected: `{expected}`")
                        lines.append(f"  - Got: `{predicted}`")
                        lines.append(f"  - Status: {status}")
                    elif error_type == "missing":
                        lines.append(f"- **{field}**: {status}")
                    elif "medicine" in error.get("field", "").lower():
                        medicine = error.get("medicine", "unknown")
                        lines.append(f"- **{medicine}**: {status}")
                    else:
                        lines.append(f"- **{field}**: {status}")
                
                if len(type_errors) > 3:
                    lines.append(f"- ... and {len(type_errors) - 3} more {error_type}(s)")
                
                lines.append("")
    
    return "\n".join(lines)


def main() -> None:
    """Run the evaluation pipeline and print results."""
    logger.info("Starting evaluation pipeline")
    
    # Run evaluation
    report = evaluate_pipeline()
    
    # Print per-image reports
    print("\n" + "=" * 80)
    print("PER-IMAGE RESULTS")
    print("=" * 80 + "\n")
    
    for result in report.get("per_image_results", []):
        print(format_per_image_report(result))
    
    # Print final report
    print("\n" + format_final_report(report))
    
    # Save reports
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Save JSON report
    json_output_path = RESULTS_DIR / "evaluation_report.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"JSON report saved to {json_output_path}")
    
    # Save Markdown report
    md_output_path = RESULTS_DIR / "evaluation_report.md"
    markdown_report = generate_markdown_report(report)
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write(markdown_report)
    logger.info(f"Markdown report saved to {md_output_path}")
    
    print("\n✅ Reports saved successfully!")
    print(f"   - JSON: {json_output_path}")
    print(f"   - Markdown: {md_output_path}")


if __name__ == "__main__":
    main()
