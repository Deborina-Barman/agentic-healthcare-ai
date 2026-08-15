# SevaCare AI - Pipeline Evaluation Report

**Date:** 2026-08-01 20:11:40

## Summary

- **Images Evaluated:** 5

## OCR Quality

| Metric | Value |
|--------|-------|
| Average CER | 1.1302 |
| Average WER | 0.9752 |
| Average Latency (ms) | 1691.82 |

## Information Extraction Quality

| Metric | Value |
|--------|-------|
| Field Accuracy | 0.1617 |
| Precision | 0.4167 |
| Recall | 0.2236 |
| F1-Score | 0.2843 |
| Average Latency (ms) | 11168.66 |

## Matching Analysis

| Category | Count |
|----------|-------|
| Exact Match After Normalization | 6 |
| Fuzzy Match (≥90% similarity) | 1 |
| Value Mismatches | 17 |
| Missing Fields | 27 |

## Per-Image Results

| Image | CER | WER | Accuracy | F1-Score |
|-------|-----|-----|----------|----------|
| prescription_1 | 1.8431 | 1.0000 | 0.0000 | 0.0000 |
| prescription_2 | 0.6656 | 0.9615 | 0.3333 | 0.5455 |
| prescription_3 | 0.8022 | 0.9545 | 0.1250 | 0.2500 |
| prescription_4 | 1.5402 | 0.9600 | 0.2500 | 0.4444 |
| prescription_5 | 0.8000 | 1.0000 | 0.1000 | 0.1818 |

## Evaluation Observations

- ✗ OCR performance needs improvement (CER > 20%)
- ✗ Information extraction needs improvement (<70% fields correct)
- ✓ Exact match after normalization: 6 fields
- ⚠ Most common issue: Missing fields (n=27)
- → OCR quality is the primary constraint on overall pipeline quality
- ⚠ 7 medicines not extracted - review extraction prompt

## Error Analysis

### prescription_1

**Extra** (3)

- **TA AZENAC-NR**: hallucinated
- **TA ADIAL**: hallucinated
- **TAZOFEL**: hallucinated

**Missing** (5)

- **date**: field_not_extracted
- **medicines**: not_extracted
- **medicines**: not_extracted
- ... and 2 more missing(s)

**Value Mismatch** (2)

- **patient_name** (60.00%% match)
  - Expected: `Prathna`
  - Got: `ATH`
  - Status: genuinely_different
- **diagnosis** (35.29%% match)
  - Expected: `['Acute GE', 'Dehydration']`
  - Got: `Acub Ge`
  - Status: genuinely_different

### prescription_2

**Extra** (3)

- **Iy.yposom Aphotoin B**: hallucinated
- **sony**: hallucinated
- **Dbvinls**: hallucinated

**Missing** (6)

- **doctor**: field_not_extracted
- **hospital**: field_not_extracted
- **date**: field_not_extracted
- ... and 3 more missing(s)

### prescription_3

**Extra** (2)

- **Auqmentn**: hallucinated
- **Hexigel gum pant**: hallucinated

**Missing** (6)

- **date**: field_not_extracted
- **hospital**: field_not_extracted
- **diagnosis**: field_not_extracted
- ... and 3 more missing(s)

**Value Mismatch** (2)

- **patient_name** (38.71%% match)
  - Expected: `Sachin Sansare`
  - Got: `Mi.Sachii Bansgae`
  - Status: genuinely_different
- **age** (50.00%% match)
  - Expected: `28`
  - Got: `20`
  - Status: value_mismatch

### prescription_4

**Missing** (4)

- **doctor**: field_not_extracted
- **hospital**: field_not_extracted
- **date**: field_not_extracted
- ... and 1 more missing(s)

**Value Mismatch** (2)

- **patient_name** (81.82%% match)
  - Expected: `Ajay Sethi`
  - Got: `MRATAY SetHI`
  - Status: genuinely_different
- **diagnosis** (82.76%% match)
  - Expected: `COVID positive`
  - Got: `CoUID+We`
  - Status: genuinely_different

### prescription_5

**Missing** (6)

- **patient_name**: field_not_extracted
- **doctor**: field_not_extracted
- **hospital**: field_not_extracted
- ... and 3 more missing(s)

**Value Mismatch** (3)

- **age** (66.67%% match)
  - Expected: `62`
  - Got: `6dyr`
  - Status: value_mismatch
- **diagnosis** (17.72%% match)
  - Expected: `['Severe sepsis', 'MODS', 'Likely lung abscess', '`
  - Got: `pnmenia`
  - Status: genuinely_different
- **clinical_notes** (42.46%% match)
  - Expected: `Patient is undergoing ICU treatment and requires c`
  - Got: `piraton pnmenia).t tutu need iepital y rp enfom an`
  - Status: genuinely_different
