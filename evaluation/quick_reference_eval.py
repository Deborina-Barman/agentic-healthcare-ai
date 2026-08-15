"""
Quick reference for running the evaluation pipeline.

Usage:
    python evaluation/evaluate_pipeline.py

The evaluator will:
1. Automatically discover all images in evaluation/images/
2. Load corresponding ground truth text and expected JSON
3. Run OCR (PaddleOCR) and extract information (Gemini)
4. Compare against ground truth and expected outputs
5. Compute CER, WER, accuracy, precision, recall, F1-score
6. Output per-image and final aggregate reports
7. Save JSON report to evaluation/results/evaluation_report.json
"""

# To run evaluation programmatically:

from evaluation.evaluate_pipeline import evaluate_pipeline, format_final_report

# Run with default paths
report = evaluate_pipeline()

# Print summary
print(format_final_report(report))

# Access individual metrics
print(f"Average CER: {report['ocr']['average_cer']:.4f}")
print(f"Average WER: {report['ocr']['average_wer']:.4f}")
print(f"Field Accuracy: {report['information_extraction']['field_accuracy']:.4f}")
print(f"F1-Score: {report['information_extraction']['f1_score']:.4f}")

# Check results per image
for result in report['per_image_results']:
    if result['status'] == 'success':
        print(f"\n{result['image']}: F1={result['information_extraction']['f1_score']:.4f}")
