# Evaluation Framework - Quick Reference

## 📊 Run the Evaluator

```bash
cd c:\Users\debor\OneDrive\Desktop\agentic_healthcare_ai
python evaluation/evaluate_pipeline.py
```

## 📄 Output Files

| File | Type | Contains |
|------|------|----------|
| `evaluation/results/evaluation_report.json` | JSON | All metrics, per-image results, error analysis |
| `evaluation/results/evaluation_report.md` | Markdown | Human-readable tables, summary, error analysis |

---

## 📈 Metrics Explained

### OCR Evaluation

| Metric | Range | Meaning |
|--------|-------|---------|
| **CER** (Character Error Rate) | 0.0 - 1.0 | Proportion of characters OCR got wrong. 0 = perfect |
| **WER** (Word Error Rate) | 0.0 - 1.0 | Proportion of words OCR got wrong. 0 = perfect |
| **Latency (ms)** | > 0 | Time to read document with OCR (excludes warm-up) |

**Example:** CER = 0.05 means 5% of characters were wrong

### Information Extraction

| Metric | Range | Meaning |
|--------|-------|---------|
| **Field Accuracy** | 0.0 - 1.0 | Proportion of correctly extracted fields |
| **Precision** | 0.0 - 1.0 | Of extracted fields, how many were correct |
| **Recall** | 0.0 - 1.0 | Of expected fields, how many were extracted |
| **F1-Score** | 0.0 - 1.0 | Harmonic mean of Precision and Recall |
| **Latency (ms)** | > 0 | Time to extract information with Gemini |

**Example:** Recall = 0.95 means 95% of expected fields were found

---

## 🔍 How Comparison Works

### Text Normalization (OCR)

```
Both texts normalized before comparison:
- Lowercase conversion
- Unicode normalization (removes accents)
- Multiple spaces → single space
- Repeated newlines removed
- Tabs → spaces
- Whitespace trimmed
```

### Field-Type Specific Normalization

**Gender:**
```
"M" → "male"       "F" → "female"
"Male" → "male"    "Female" → "female"
"Boy" → "male"     "Girl" → "female"
```

**Medicine:**
```
"Augmentin." → "augmentin"
"Augmentin-" → "augmentin"
"AUGMENTIN" → "augmentin"
```

**Duration:**
```
"3day" → "3 days"
"Once daily" → "1 time daily"
"D" → "days"
"W" → "weeks"
```

**Status:**
```
"+ve" → "positive"
"-ve" → "negative"
"COVID +ve" → "covid positive"
```

---

## ❌ Error Analysis

### Types of Errors Detected

| Error Type | Example | Impact |
|-----------|---------|--------|
| **Missing Field** | Expected field not extracted | Reduces Recall |
| **Incorrect Value** | Wrong text or number | Reduces Precision |
| **Missing Medicine** | Medicine not extracted | Tracked separately |
| **Extra Medicine** | Extra medicine extracted | False positive |
| **Type Mismatch** | Expected number, got text | Incorrect field |

### Finding Errors

**In JSON report:**
```json
"error_analysis": [
  {
    "image": "prescription_1",
    "field": "patient_name",
    "error": "value mismatch: expected 'Sachin', got 'Sachii'"
  }
]
```

**In Markdown report:**
```markdown
## Error Analysis

### prescription_1
- **Field:** patient_name
  **Error:** value mismatch: expected 'Sachin', got 'Sachii'
```

---

## 📐 Metrics Calculation

### True Positives, False Positives, False Negatives

```
True Positives (TP):   Fields extracted correctly
False Positives (FP):  Fields extracted with wrong values
False Negatives (FN):  Fields not extracted (missing)
```

### From TP/FP/FN to Metrics

```
Accuracy  = TP / (TP + FP + FN)
Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
F1-Score  = 2 × (Precision × Recall) / (Precision + Recall)
```

### Example

```
Total Fields: 8
Matched: 7
Missing: 0
Incorrect: 1

TP = 7, FP = 1, FN = 0

Accuracy  = 7 / 8 = 0.875 (87.5%)
Precision = 7 / 8 = 0.875 (87.5%)
Recall    = 7 / 7 = 1.0 (100%)
F1-Score  = 2 × (0.875 × 1.0) / (0.875 + 1.0) = 0.933
```

---

## 🎯 Interpretation Guide

### OCR Quality

| CER | WER | Quality |
|-----|-----|---------|
| < 0.02 | < 0.05 | Excellent |
| 0.02-0.05 | 0.05-0.10 | Good |
| 0.05-0.10 | 0.10-0.20 | Fair |
| > 0.10 | > 0.20 | Poor |

### Information Extraction Quality

| Accuracy | F1-Score | Quality |
|----------|----------|---------|
| > 0.95 | > 0.95 | Excellent |
| 0.90-0.95 | 0.90-0.95 | Good |
| 0.80-0.90 | 0.80-0.90 | Fair |
| < 0.80 | < 0.80 | Poor |

---

## 🐍 Using in Code

### Basic Usage

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

# Run full evaluation
report = evaluate_pipeline()

# Access metrics
ocr_cer = report['ocr']['average_cer']
extraction_accuracy = report['information_extraction']['field_accuracy']
pipeline_latency = report['pipeline']['average_total_latency_ms']

print(f"CER: {ocr_cer:.4f}")
print(f"Field Accuracy: {extraction_accuracy:.4f}")
print(f"Latency: {pipeline_latency:.2f}ms")
```

### Normalize Text

```python
from evaluation.evaluate_pipeline import normalize_text

text = "COVID-19  Test"
normalized = normalize_text(text)
# Result: "covid 19 test"
```

### Normalize Field Value

```python
from evaluation.evaluate_pipeline import normalize_field_value

# Gender normalization
normalize_field_value("M", "gender")
# Result: "male"

# Duration normalization
normalize_field_value("3day", "duration")
# Result: "3 days"

# Medicine normalization
normalize_field_value("Augmentin.", "medicine")
# Result: "augmentin"
```

### Compare Strings Semantically

```python
from evaluation.evaluate_pipeline import compare_strings_semantic

# Compare with field type awareness
result = compare_strings_semantic("M", "Male", "gender")
# Result: True

result = compare_strings_semantic("3day", "3 days", "duration")
# Result: True
```

---

## 🔧 Configuration

### Default Paths

```python
IMAGES_DIR = "evaluation/images"
GROUND_TRUTH_DIR = "evaluation/ground_truth"
EXPECTED_JSON_DIR = "evaluation/expected_json"
RESULTS_DIR = "evaluation/results"
```

### Custom Paths

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline(
    images_dir="/path/to/images",
    ground_truth_dir="/path/to/ground_truth",
    expected_json_dir="/path/to/expected_json",
)
```

### Required File Structure

```
evaluation/
├── images/
│   ├── prescription_1.jpg
│   ├── prescription_2.jpg
│   └── ...
├── ground_truth/
│   ├── prescription_1.txt  (OCR reference text)
│   ├── prescription_2.txt
│   └── ...
├── expected_json/
│   ├── prescription_1.json (Expected extracted JSON)
│   ├── prescription_2.json
│   └── ...
└── results/
    ├── evaluation_report.json (Generated)
    └── evaluation_report.md   (Generated)
```

---

## 📝 Ground Truth Format

### Text File (OCR Reference)

`evaluation/ground_truth/prescription_1.txt`:
```
Doctor: Dr. R. Keshwani
Patient: Sachin Sansare
Age: 28
Gender: M
Hospital: Aditya Birla Hospital
Diagnosis: Acute Gastroenteritis
Medicines:
1. Oflazest OZ - 1-1
2. Azevac MR - 1-1
Duration: 3 days
```

### JSON File (Expected Extraction)

`evaluation/expected_json/prescription_1.json`:
```json
{
  "doctor": "Dr. R. Keshwani",
  "patient": "Sachin Sansare",
  "age": 28,
  "gender": "M",
  "hospital": "Aditya Birla Hospital",
  "diagnosis": "Acute Gastroenteritis",
  "medicines": [
    {"name": "Oflazest OZ", "frequency": "1-1"},
    {"name": "Azevac MR", "frequency": "1-1"}
  ],
  "duration": "3 days"
}
```

---

## 🚀 Performance Considerations

### Warm-up OCR

First OCR call loads PaddleOCR models (~2-5 seconds). This time is **excluded** from averages.

```
Timeline:
├── Warm-up OCR (excluded from averages)
├── Evaluation Image 1 (included)
├── Evaluation Image 2 (included)
├── ...
└── Report generation
```

### Latency Averages

- **OCR Latency:** Time to read document (excludes warm-up)
- **Extraction Latency:** Time to extract clinical information
- **Total Latency:** OCR + Extraction time

---

## 🐛 Common Issues

### Issue: High CER/WER

**Possible causes:**
- Poor image quality
- Small text
- Handwritten prescriptions
- Non-Latin scripts

**Check:** `error_analysis` for specific character/word errors

### Issue: Low Field Accuracy

**Possible causes:**
- OCR errors propagated to extraction
- Ambiguous instructions to Gemini
- Missing or incorrect ground truth

**Check:** `missing_fields` and `incorrect_fields` in report

### Issue: Missing Medicines

**Possible causes:**
- Medicines not clearly written on prescription
- OCR quality issues with medicine names
- Gemini couldn't parse medicine list

**Check:** `medicine` errors in error_analysis

---

## ✨ Key Features

✅ **Semantic Normalization:** Understands field types  
✅ **Smart Comparison:** Matches similar values  
✅ **Detailed Errors:** Shows exactly what went wrong  
✅ **Multiple Reports:** JSON + Markdown  
✅ **Warm-up Handling:** Accurate latency measurement  
✅ **Type Hints:** Full type annotations  
✅ **Logging:** Comprehensive debug info  
✅ **Error Handling:** Graceful failure recovery  

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| `EVALUATION_IMPROVEMENTS_V2.md` | Detailed improvements explanation |
| `EVALUATION_UPGRADE_GUIDE.md` | Migration and usage guide |
| `QUICK_REFERENCE_EVAL.md` | Quick reference (this document) |

---

## 🎓 Examples

### Example 1: Evaluate and Print Metrics

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline()

print("=== OCR ===")
print(f"Average CER: {report['ocr']['average_cer']:.4f}")
print(f"Average WER: {report['ocr']['average_wer']:.4f}")

print("\n=== Information Extraction ===")
print(f"Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
print(f"F1-Score: {report['information_extraction']['f1_score']:.4f}")
```

### Example 2: Analyze Errors

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline()

print("Errors by type:")
error_types = {}
for error in report['error_analysis']:
    error_type = error.get('error', 'unknown')
    error_types[error_type] = error_types.get(error_type, 0) + 1

for error_type, count in sorted(error_types.items(), 
                                 key=lambda x: x[1], 
                                 reverse=True):
    print(f"  {error_type}: {count}")
```

### Example 3: Track Trends

```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline()

# Log metrics for tracking over time
metrics = {
    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    'cer': report['ocr']['average_cer'],
    'wer': report['ocr']['average_wer'],
    'field_accuracy': report['information_extraction']['field_accuracy'],
    'f1_score': report['information_extraction']['f1_score'],
}

# Save to CSV/database for trend analysis
```

---

## 💡 Tips

1. **Start with error analysis:** Look at what's failing
2. **Check OCR first:** Extraction depends on OCR quality
3. **Track trends:** Run evaluator regularly to monitor quality
4. **Use exact ground truth:** Quality of evaluation depends on ground truth accuracy
5. **Per-image analysis:** Look at specific failing images for patterns
6. **Normalize expectations:** Some error is expected in real-world data

---

## 📞 Support

**For questions about:**
- Framework usage → See this document
- Specific metrics → See Metrics Explained section
- Error analysis → See Error Analysis section
- Code examples → See Examples section

---

**Status:** ✅ Ready to use  
**Last Updated:** 2026-08-01  
**Version:** 2.0 (Enhanced)
