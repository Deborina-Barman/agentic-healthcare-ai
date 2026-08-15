# Evaluation Framework Documentation

## Overview

The evaluation framework provides comprehensive assessment of the OCR and information extraction pipeline used by SevaCare AI.

**Key Components:**
- `evaluate_pipeline.py` - Main evaluation engine
- Dataset structure with images, ground truth, and expected outputs

## What Gets Evaluated

### 1. OCR Quality
- **Character Error Rate (CER)**: Measures character-level differences between OCR output and ground truth
- **Word Error Rate (WER)**: Measures word-level differences between OCR output and ground truth
- **Latency**: Time taken by PaddleOCR to process the image

### 2. Information Extraction Quality
- **Field Accuracy**: Proportion of fields correctly extracted
- **Precision**: True positives / (True positives + False positives)
- **Recall**: True positives / (True positives + False negatives)
- **F1-Score**: Harmonic mean of precision and recall
- **Missing Fields**: Fields present in expected output but not extracted
- **Incorrect Fields**: Fields with wrong values
- **Latency**: Time taken by Gemini to extract information

### 3. Pipeline Latency
- **Total Latency**: OCR latency + Gemini latency combined

## Dataset Structure

Place your evaluation data in the following structure:

```
evaluation/
├── images/
│   ├── prescription_1.jpg
│   ├── prescription_2.jpg
│   └── ...
├── ground_truth/
│   ├── prescription_1.txt
│   ├── prescription_2.txt
│   └── ...
├── expected_json/
│   ├── prescription_1.json
│   ├── prescription_2.json
│   └── ...
└── results/
    └── evaluation_report.json
```

### File Formats

**Ground Truth Text** (`*.txt`):
- Raw OCR transcription that serves as the reference
- Plain text format
- Example: `prescription_1.txt`

**Expected JSON** (`*.json`):
- Expected structured output after information extraction
- Should match the schema that Gemini produces
- Example: `prescription_1.json`

## Usage

### Basic Usage

Run the evaluator with default dataset paths:

```bash
python evaluation/evaluate_pipeline.py
```

### Programmatic Usage

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

# Run evaluation
report = evaluate_pipeline()

# Access results
print(f"Images evaluated: {report['images_evaluated']}")
print(f"Average CER: {report['ocr']['average_cer']:.4f}")
print(f"Average WER: {report['ocr']['average_wer']:.4f}")
print(f"Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
```

### Custom Paths

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline(
    images_dir="path/to/images",
    ground_truth_dir="path/to/ground_truth",
    expected_json_dir="path/to/expected_json"
)
```

## Output Format

### Console Output

The evaluator prints:
1. **Per-image reports** with detailed metrics
2. **Final summary** with averages and totals

Example:
```
============================================================
EVALUATION REPORT
============================================================

Summary:
  Images Evaluated: 5

OCR Evaluation:
  Average CER: 0.0523
  Average WER: 0.1234
  Average Latency: 2345.67ms

Information Extraction:
  Average Field Accuracy: 0.8950
  Average Precision: 0.9120
  Average Recall: 0.8750
  Average F1-Score: 0.8930
  Total Missing Fields: 3
  Total Incorrect Fields: 2

Pipeline:
  Average Total Latency: 5678.90ms
============================================================
```

### JSON Output

A structured JSON report is saved to `evaluation/results/evaluation_report.json`:

```json
{
  "status": "success",
  "images_evaluated": 5,
  "ocr": {
    "average_cer": 0.0523,
    "average_wer": 0.1234,
    "average_latency_ms": 2345.67
  },
  "information_extraction": {
    "field_accuracy": 0.8950,
    "precision": 0.9120,
    "recall": 0.8750,
    "f1_score": 0.8930,
    "missing_fields": 3,
    "incorrect_fields": 2
  },
  "pipeline": {
    "average_total_latency_ms": 5678.90
  },
  "per_image_results": [
    {
      "image": "prescription_1",
      "status": "success",
      "ocr": {
        "latency_ms": 2100.50,
        "cer": 0.0450,
        "wer": 0.1100,
        "output_length": 500,
        "ground_truth_length": 520
      },
      "information_extraction": {
        "latency_ms": 3500.20,
        "field_accuracy": 0.9000,
        "precision": 0.9200,
        "recall": 0.8800,
        "f1_score": 0.9000,
        "total_fields": 10,
        "matched_fields": 9,
        "missing_fields": ["field_name"],
        "incorrect_fields": []
      },
      "pipeline": {
        "total_latency_ms": 5600.70
      },
      "errors": []
    }
  ]
}
```

## Metrics Explained

### Character Error Rate (CER)
- Formula: Edit distance / Reference length
- Range: 0 (perfect) to 1+ (very poor)
- Lower is better
- Calculated using Levenshtein distance at character level

### Word Error Rate (WER)
- Formula: Edit distance / Reference length (in words)
- Range: 0 (perfect) to 1+ (very poor)
- Lower is better
- Calculated using Levenshtein distance at word level

### Field Accuracy
- Formula: Matched fields / Total expected fields
- Range: 0 to 1
- Higher is better
- Counts both missing and incorrect fields as failures

### Precision
- Formula: True Positives / (True Positives + False Positives)
- Range: 0 to 1
- Higher is better
- Indicates reliability of extracted information

### Recall
- Formula: True Positives / (True Positives + False Negatives)
- Range: 0 to 1
- Higher is better
- Indicates completeness of extraction

### F1-Score
- Formula: 2 * (Precision * Recall) / (Precision + Recall)
- Range: 0 to 1
- Higher is better
- Harmonic mean of precision and recall

## Implementation Details

### CER/WER Calculation
- Uses the `jiwer` library (pip install jiwer)
- Provides reliable, standard implementation
- Handles edge cases and empty strings gracefully

### JSON Comparison
- Recursively flattens nested structures
- Compares field by field
- Case-insensitive value comparison
- Whitespace is trimmed before comparison

### Error Handling
- Gracefully handles missing ground truth/expected JSON
- Logs warnings for missing files
- Continues evaluation for valid images
- Detailed error messages in output

## Requirements

Dependencies are listed in `requirements.txt`. Install with:

```bash
pip install -r requirements.txt
```

Key dependencies:
- `jiwer` - CER/WER calculation
- `google-genai` - Gemini API access
- `pillow` - Image processing
- `python-dotenv` - Environment variables
- Others as specified

## Automatic Image Discovery

The evaluator automatically discovers all images in the dataset without requiring configuration:

1. Scans `evaluation/images/` for all `.jpg` and `.png` files
2. For each image, looks for matching:
   - Ground truth file: `evaluation/ground_truth/{image_name}.txt`
   - Expected JSON: `evaluation/expected_json/{image_name}.json`
3. Skips images with missing files (with warning)
4. Evaluates all valid images

This means you can add new evaluation images simply by placing them in the correct folders with matching filenames.

## Important Notes

### ⚠️ Do Not Modify Production Code

This evaluation framework only modifies:
- `evaluation/evaluate_pipeline.py` (new file)
- `evaluation/results/evaluation_report.json` (output)
- `requirements.txt` (added jiwer)

**No changes to:**
- LangGraph workflow
- ChatController
- Reader Agent
- PaddleOCR implementation
- Gemini Information Extractor
- RAG pipeline
- FAISS
- Other production services

### Ground Truth Accuracy

The quality of evaluation depends on ground truth accuracy. Ensure:
- Ground truth text files contain exact OCR transcriptions
- Expected JSON files contain the correct structured data
- Files are correctly named and placed

### Network Requirements

The evaluator requires internet connection for:
- Google Gemini API calls (information extraction)
- Ensure `GEMINI_API_KEY` environment variable is set

### Performance

Typical performance (varies with hardware):
- OCR: 2-5 seconds per image
- Gemini extraction: 3-10 seconds per image
- Total: 5-15 seconds per image

## Troubleshooting

### "No images found" error
- Check that images are in `evaluation/images/`
- Verify filenames end with `.jpg` or `.png`
- Check file permissions

### Missing ground truth or expected JSON
- Ensure files exist in correct directories
- Check filename matches image name exactly (before extension)
- Verify file permissions

### Gemini API errors
- Verify `GEMINI_API_KEY` is set
- Check API quota and rate limits
- Ensure internet connection is active

### Import errors
- Run `pip install -r requirements.txt`
- Ensure you're in the project root directory
- Verify Python version >= 3.8

## Adding More Evaluation Images

1. Add new image to `evaluation/images/`: `prescription_N.jpg`
2. Add ground truth to `evaluation/ground_truth/`: `prescription_N.txt`
3. Add expected JSON to `evaluation/expected_json/`: `prescription_N.json`
4. Run `python evaluation/evaluate_pipeline.py`

No code changes needed - the evaluator automatically discovers new images.
