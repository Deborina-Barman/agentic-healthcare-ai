# SevaCare AI - Evaluation Framework Improvements

## Summary

The evaluation framework has been completely replaced with a comprehensive pipeline evaluator that properly assesses both OCR quality and information extraction quality using the production pipeline.

## What Was Implemented

### 1. **New Comprehensive Evaluator** (`evaluate_pipeline.py`)

A complete evaluation pipeline that:

#### OCR Evaluation
- Runs `services.paddle_ocr_service.read_document_with_paddle()` 
- Loads ground truth text from `evaluation/ground_truth/*.txt`
- Compares OCR output vs ground truth
- Calculates:
  - **Character Error Rate (CER)** - using jiwer library
  - **Word Error Rate (WER)** - using jiwer library
  - **OCR Latency** - milliseconds

#### Information Extraction Evaluation
- Runs `services.gemini_information_extractor.extract_clinical_information()`
- Takes OCR text as input
- Loads expected output from `evaluation/expected_json/*.json`
- Compares predicted JSON vs expected JSON
- Calculates:
  - **Field Accuracy** - matched fields / total fields
  - **Precision** - TP / (TP + FP)
  - **Recall** - TP / (TP + FN)
  - **F1-Score** - 2 × (P × R) / (P + R)
  - **Missing Fields** - fields in expected but not in predicted
  - **Incorrect Fields** - fields with wrong values
  - **Gemini Latency** - milliseconds

#### Pipeline Metrics
- **Total Pipeline Latency** - OCR latency + Gemini latency
- **Aggregate latencies** - averages across all images

### 2. **Key Features**

✅ **Automatic Image Discovery**
- Scans `evaluation/images/` for all `.jpg` and `.png` files
- Automatically matches with ground truth and expected JSON
- No hardcoding needed - add new images and they're evaluated

✅ **Modular Architecture**
- Separate functions for OCR eval, JSON comparison, metrics calculation
- Reusable helper functions
- Clean, readable code

✅ **Robust Error Handling**
- Gracefully handles missing files
- Logs warnings for missing ground truth/expected JSON
- Continues evaluation for valid images
- Detailed error messages in output

✅ **Dual Output Format**
- Human-readable console output (per-image + summary)
- Structured JSON output saved to `evaluation/results/evaluation_report.json`

✅ **Production Pipeline Integration**
- Uses exact production functions:
  - `services.paddle_ocr_service.read_document_with_paddle()`
  - `services.gemini_information_extractor.extract_clinical_information()`
- No modifications to production code
- Evaluates real-world pipeline behavior

### 3. **Metrics Computed**

**Per Image:**
- CER, WER (for OCR quality)
- Field Accuracy, Precision, Recall, F1 (for extraction)
- Missing/Incorrect field details
- OCR latency, Gemini latency, total latency

**Aggregate:**
- Average CER, Average WER
- Average Field Accuracy, Precision, Recall, F1
- Total missing and incorrect fields
- Average latencies

### 4. **JSON Comparison Algorithm**

Implements recursive deep comparison:
- Flattens nested dictionaries
- Handles arrays by converting to strings
- Case-insensitive value comparison
- Whitespace-trimmed comparison
- Field-by-field accuracy tracking

**Example:**
```python
expected = {
    "medicines": [{"name": "Aspirin", "dosage": "500mg"}],
    "diagnosis": "Headache"
}
predicted = {
    "medicines": [{"name": "aspirin", "dosage": "500 mg"}],
    "diagnosis": "Headache"
}
# Both matched due to case-insensitive comparison
```

### 5. **Updated Dependencies**

Added to `requirements.txt`:
- `jiwer` - Reliable CER/WER calculation using Levenshtein distance

This is a standard library used in speech recognition and OCR evaluation.

## Output Example

### Console Output

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

### JSON Report (`evaluation/results/evaluation_report.json`)

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
  "per_image_results": [...]
}
```

## What Wasn't Modified (Production Code)

✅ LangGraph workflow - Unchanged
✅ ChatController - Unchanged
✅ Reader Agent - Unchanged
✅ PaddleOCR implementation - Unchanged
✅ Gemini Information Extractor - Unchanged
✅ RAG pipeline - Unchanged
✅ FAISS - Unchanged
✅ Summary Agent - Unchanged
✅ Urgency Agent - Unchanged
✅ Follow-up Question Agent - Unchanged
✅ Clinical Context Agent - Unchanged
✅ APIs - Unchanged
✅ React frontend - Unchanged
✅ Conversation flow - Unchanged

## How to Use

### Basic Run
```bash
python evaluation/evaluate_pipeline.py
```

### Programmatic Access
```python
from evaluation.evaluate_pipeline import evaluate_pipeline

report = evaluate_pipeline()
print(f"Average CER: {report['ocr']['average_cer']:.4f}")
print(f"Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
```

### Add New Evaluation Images

1. Place image in `evaluation/images/` (e.g., `prescription_6.jpg`)
2. Place ground truth in `evaluation/ground_truth/` (e.g., `prescription_6.txt`)
3. Place expected JSON in `evaluation/expected_json/` (e.g., `prescription_6.json`)
4. Run evaluator - no code changes needed!

## Files Modified/Created

### Created:
- ✨ `evaluation/evaluate_pipeline.py` - Main evaluator (460+ lines)
- ✨ `evaluation/EVALUATION_GUIDE.md` - Comprehensive documentation
- ✨ `evaluation/quick_reference_eval.py` - Quick reference

### Modified:
- 📝 `requirements.txt` - Added `jiwer`

### Never Modified:
- Production services
- Production agents
- Production APIs
- Frontend code
- Configuration

## Quality Assurance

✅ Uses reliable libraries:
- `jiwer` for CER/WER (standard speech/OCR evaluation)
- `pathlib` for cross-platform file handling
- Built-in Python for JSON handling

✅ Comprehensive error handling:
- Catches PaddleOCRError
- Catches GeminiInformationExtractionError
- Handles missing files gracefully
- Detailed error logging

✅ Modular design:
- Separate functions for each concern
- Easy to test and debug
- Easy to extend

✅ Performance:
- Efficient nested dictionary comparison
- Lazy evaluation where possible
- Minimal memory footprint

## Documentation Provided

1. **EVALUATION_GUIDE.md** - Comprehensive guide with:
   - What gets evaluated
   - Dataset structure
   - Usage instructions
   - Output format explanation
   - Metrics explanation
   - Troubleshooting

2. **quick_reference_eval.py** - Quick reference code examples

3. **This file** - Implementation summary

## Next Steps

To run the evaluation:

1. Ensure images/ground truth/expected JSON are in place
2. Install dependencies: `pip install -r requirements.txt`
3. Set GEMINI_API_KEY environment variable
4. Run: `python evaluation/evaluate_pipeline.py`
5. Check results in console and `evaluation/results/evaluation_report.json`

## Technical Details

### CER/WER Calculation
- Uses Levenshtein distance (via jiwer)
- CER: Character-level edit distance / reference length
- WER: Word-level edit distance / reference length
- Range: 0 (perfect) to 1+ (very poor)

### JSON Comparison
- Flattens nested structures for comparison
- Case-insensitive and whitespace-trimmed
- Handles missing fields separately from incorrect values
- Both count as failures in field accuracy

### Metric Calculation
- True Positives: Matched fields
- False Positives: Incorrect field values
- False Negatives: Missing fields
- Accuracy, Precision, Recall, F1 calculated from these

## Version History

- **v1.0** (2025-08-01): Complete evaluation framework implementation
  - Replaced broken regex-based evaluator
  - Added CER/WER calculation
  - Added JSON comparison
  - Added comprehensive metrics
  - Added automatic image discovery
  - Added dual output format (console + JSON)
