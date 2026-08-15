# SevaCare AI Evaluation Framework - Complete Guide

## 🎯 Overview

The SevaCare AI evaluation framework provides comprehensive assessment of both OCR quality and information extraction quality using the production pipeline.

**Status: ✅ Complete and Ready for Use**

---

## 📊 What Gets Evaluated

### 1. OCR Quality
Measures how accurately PaddleOCR extracts text from medical documents.

**Metrics:**
- **CER (Character Error Rate):** 0-1+ scale, lower is better
- **WER (Word Error Rate):** 0-1+ scale, lower is better
- **Latency:** Time to process image in milliseconds

**How it works:**
1. Image → PaddleOCR → Raw text
2. Compare with ground truth text file
3. Calculate character-level and word-level differences

### 2. Information Extraction Quality
Measures how accurately Gemini extracts structured data from OCR text.

**Metrics:**
- **Field Accuracy:** % of fields correctly extracted (0-1)
- **Precision:** True positives / (True positives + False positives)
- **Recall:** True positives / (True positives + False negatives)
- **F1-Score:** Harmonic mean of precision and recall
- **Missing Fields:** Count of fields not extracted
- **Incorrect Fields:** Count of fields with wrong values
- **Latency:** Time to extract in milliseconds

**How it works:**
1. Raw OCR text → Gemini → Extracted JSON
2. Compare with expected JSON file
3. Calculate field-by-field accuracy metrics

### 3. Pipeline Metrics
Measures overall pipeline performance.

**Metrics:**
- **Total Pipeline Latency:** OCR latency + Gemini latency
- **Average Latencies:** Across all evaluation images

---

## 📁 Dataset Structure

Place evaluation files in this structure:

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
    └── evaluation_report.json (generated)
```

### File Formats

**Ground Truth Text (*.txt):**
- Plain text OCR transcription
- Should match what the OCR engine should ideally output
- No JSON or special formatting

Example `prescription_1.txt`:
```
Doctor: Dr. R. Keshwani
Patient: Ms. Prathna
Date: 15-03-2022

Diagnosis:
Acute GE
Dehydration

Medicines:
1. Oflazest OZ - 1-1
2. Azevac MR - 1-1
```

**Expected JSON (*.json):**
- Structured data in JSON format
- Should match the schema that Gemini produces
- Can have nested structures, arrays, objects

Example `prescription_1.json`:
```json
{
  "patient_name": "Prathna",
  "date": "15-03-2022",
  "diagnosis": ["Acute GE", "Dehydration"],
  "medicines": [
    {"name": "Oflazest OZ", "frequency": "1-1"},
    {"name": "Azevac MR", "frequency": "1-1"}
  ],
  "duration": "3 days"
}
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variable
```bash
# Windows
set GEMINI_API_KEY=your-key-here

# Linux/Mac
export GEMINI_API_KEY=your-key-here
```

### 3. Run Evaluator
```bash
python evaluation/evaluate_pipeline.py
```

### 4. View Results
- Console output shows per-image and final summary
- JSON report saved to `evaluation/results/evaluation_report.json`

---

## 📈 Output Examples

### Console Output

```
============================================================
PER-IMAGE RESULTS
============================================================

------------------------------------------------------------
Image: prescription_1
Status: SUCCESS

OCR Metrics:
  CER: 0.0450
  WER: 0.1100
  Latency: 2100.50ms

Information Extraction:
  Field Accuracy: 0.9000
  Precision: 0.9200
  Recall: 0.8800
  F1-Score: 0.9000
  Latency: 3500.20ms
  Matched Fields: 9/10
  Missing Fields: field_name

Pipeline:
  Total Latency: 5600.70ms
------------------------------------------------------------

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

File: `evaluation/results/evaluation_report.json`

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

---

## 📚 Understanding the Metrics

### CER (Character Error Rate)
- **What it measures:** Character-level accuracy
- **Formula:** Edit distance / Reference length (in characters)
- **Range:** 0 (perfect) to 1+ (very poor)
- **Lower is better**
- **Example:**
  - Ground truth: "Aspirin 500mg" (13 chars)
  - OCR output: "Asprin 500mg" (12 chars, missing 'i')
  - CER ≈ 0.077

### WER (Word Error Rate)
- **What it measures:** Word-level accuracy
- **Formula:** Edit distance / Reference length (in words)
- **Range:** 0 (perfect) to 1+ (very poor)
- **Lower is better**
- **Example:**
  - Ground truth: "Doctor Smith gave medicine" (5 words)
  - OCR output: "Docter Smth gave medicine" (5 words, 2 wrong)
  - WER ≈ 0.40

### Field Accuracy
- **What it measures:** Proportion of fields correctly extracted
- **Formula:** Matched fields / Total expected fields
- **Range:** 0 to 1 (0% to 100%)
- **Higher is better**
- **Counts:**
  - ✓ Matched: Extracted value matches expected value
  - ✗ Missing: Field not in extracted output
  - ✗ Incorrect: Field present but value wrong

### Precision
- **What it measures:** Reliability of extracted information
- **Formula:** TP / (TP + FP)
  - TP = Matched fields
  - FP = Incorrect values
- **Range:** 0 to 1
- **Higher is better**
- **Interpretation:** Of all extracted fields, what % were correct?

### Recall
- **What it measures:** Completeness of extraction
- **Formula:** TP / (TP + FN)
  - TP = Matched fields
  - FN = Missing fields
- **Range:** 0 to 1
- **Higher is better**
- **Interpretation:** Of all expected fields, what % were extracted?

### F1-Score
- **What it measures:** Balance between precision and recall
- **Formula:** 2 × (Precision × Recall) / (Precision + Recall)
- **Range:** 0 to 1
- **Higher is better**
- **Interpretation:** Single metric combining precision and recall

### Example Calculation

```
Expected fields: 10
Matched fields: 9
Incorrect values: 1
Missing fields: 0

TP = 9
FP = 1
FN = 0

Accuracy = 9 / 10 = 0.90
Precision = 9 / (9 + 1) = 0.90
Recall = 9 / (9 + 0) = 1.00
F1 = 2 × (0.90 × 1.00) / (0.90 + 1.00) = 0.947
```

---

## 🔧 Advanced Usage

### Programmatic Access

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

# Run evaluation with default paths
report = evaluate_pipeline()

# Access specific metrics
print(f"Average CER: {report['ocr']['average_cer']:.4f}")
print(f"Average WER: {report['ocr']['average_wer']:.4f}")
print(f"Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
print(f"F1-Score: {report['information_extraction']['f1_score']:.4f}")

# Check per-image results
for result in report['per_image_results']:
    if result['status'] == 'success':
        print(f"{result['image']}: F1={result['information_extraction']['f1_score']:.4f}")
```

### Custom Paths

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline(
    images_dir="/custom/path/to/images",
    ground_truth_dir="/custom/path/to/ground_truth",
    expected_json_dir="/custom/path/to/expected_json"
)
```

### Formatting Functions

```python
from evaluation.evaluate_pipeline import format_final_report, format_per_image_report

report = evaluate_pipeline()

# Print formatted final report
print(format_final_report(report))

# Print per-image reports
for result in report['per_image_results']:
    print(format_per_image_report(result))
```

---

## 🐛 Troubleshooting

### "No images found" error
- Check that images exist in `evaluation/images/`
- Verify filenames end with `.jpg` or `.png`
- Check file permissions

### Missing ground truth or expected JSON
- Ensure files exist in correct directories
- Check filenames match image names exactly (before extension)
- Example: `prescription_1.jpg` needs `prescription_1.txt` and `prescription_1.json`

### Gemini API errors
- Verify `GEMINI_API_KEY` environment variable is set
- Check API quota and rate limits
- Ensure internet connection is active
- Check API key is valid

### Import errors
- Run `pip install -r requirements.txt`
- Verify you're in project root directory
- Python version should be >= 3.8

### File not found errors
- Verify dataset directory structure
- Check file permissions
- Ensure file encoding is UTF-8

---

## ⚡ Performance

Typical performance (varies with hardware and network):

- **Per image:**
  - OCR: 2-5 seconds
  - Gemini extraction: 3-10 seconds
  - Total: 5-15 seconds per image

- **Batch of 5 images:**
  - Total time: ~5 minutes

- **Batch of 20 images:**
  - Total time: ~20 minutes

### Optimization Tips

1. Ensure stable internet connection
2. Run during off-peak hours (less API congestion)
3. Pre-process images to optimal resolution (300-600 dpi)
4. Monitor Gemini API rate limits

---

## 📋 Implementation Details

### Architecture

```
evaluate_pipeline.py
├── _load_image_bytes()          - Load image file
├── _load_ground_truth()         - Load text file
├── _load_expected_json()        - Load JSON file
├── _flatten_dict()              - Flatten nested structures
├── calculate_cer_wer()          - Compute CER/WER using jiwer
├── deep_compare_json()          - Recursive JSON comparison
├── calculate_metrics()          - Compute P/R/F1
├── evaluate_single_image()      - Evaluate one image
├── evaluate_pipeline()          - Main orchestrator
├── format_per_image_report()    - Format output
├── format_final_report()        - Format summary
└── main()                       - CLI entry point
```

### Dependencies

- **jiwer:** CER/WER calculation (industry standard)
- **google-genai:** Gemini API access
- **pillow:** Image processing
- **python-dotenv:** Environment variables
- Standard library: json, logging, pathlib, time

### Design Principles

✅ **Production Integration:** Uses actual production services  
✅ **No Modifications:** Doesn't change production code  
✅ **Auto-Discovery:** Finds images automatically  
✅ **Error Handling:** Graceful error recovery  
✅ **Modular:** Reusable functions  
✅ **Documented:** Comprehensive docstrings  
✅ **Tested:** Type hints and validation  

---

## 📖 Documentation Files

- **`evaluation/evaluate_pipeline.py`** - Main evaluator (500+ lines)
- **`evaluation/EVALUATION_GUIDE.md`** - Detailed user guide
- **`evaluation/quick_reference_eval.py`** - Code examples
- **`EVALUATION_IMPROVEMENTS.md`** - Implementation summary
- **`IMPLEMENTATION_CHECKLIST.md`** - Verification checklist
- **`EVALUATION_VISUAL_SUMMARY.md`** - Visual overview
- **`README_EVALUATOR.md`** - This file

---

## ✅ Verification Checklist

Run this after setting up the evaluator:

- [ ] Dataset files exist in correct directories
- [ ] `GEMINI_API_KEY` environment variable is set
- [ ] Dependencies installed: `pip install -r requirements.txt`
- [ ] Can run: `python evaluation/evaluate_pipeline.py`
- [ ] Console output shows per-image results
- [ ] JSON report generated in `evaluation/results/`
- [ ] All metrics are numeric values
- [ ] No errors in output

---

## 🎓 Learning Resources

### Understanding OCR Evaluation
- CER/WER are industry standard metrics
- Based on Levenshtein distance
- Used in speech recognition and OCR

### Understanding Information Extraction Evaluation
- Field accuracy measures extraction quality
- Precision/Recall/F1 are standard ML metrics
- Commonly used in NLP and IE tasks

### Further Reading
- jiwer documentation: https://github.com/jitsi/jiwer
- Levenshtein distance: https://en.wikipedia.org/wiki/Levenshtein_distance
- Precision/Recall: https://en.wikipedia.org/wiki/Precision_and_recall

---

## 📝 Notes

- The evaluator does not modify any production code
- Ground truth accuracy is critical for meaningful results
- Evaluation latencies depend on hardware and network
- JSON comparison is case-insensitive but matches structure strictly

---

**Last Updated:** 2025-08-01  
**Status:** ✅ Production Ready  
**Version:** 1.0
