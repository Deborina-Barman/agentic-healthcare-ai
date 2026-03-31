# Agentic Healthcare AI

An end-to-end **AI clinical intake assistant** that collects patient history through guided conversation, structures symptoms into NLICE format, predicts urgency, and generates a clinician-friendly summary report.

## What This Project Does

- Runs an interactive **Streamlit** intake app.
- Collects demographics, chief complaint, symptom timeline, and medical history.
- Uses a question-generation agent to ask follow-up clinical questions.
- Structures symptoms into **NLICE**:
  - Nature
  - Location
  - Intensity
  - Chronology
  - Excitation
- Applies an ML urgency classifier (`LOW`, `MODERATE`, `HIGH`, `EMERGENCY`).
- Generates a final clinical summary and downloadable PDF.
- Optionally reads prescription images using Gemini vision.

## Tech Stack

- Python
- Streamlit
- Google Gemini (`google-genai`)
- scikit-learn + joblib
- pandas
- Pillow

## Project Structure

```text
agentic_healthcare_ai/
|- agents/
|  |- complaint_agent.py
|  |- question_agent.py
|  |- reader_agent.py
|  |- clinical_synthesis_agent.py
|  |- urgency_classifier_agent.py
|  |- clinical_context_agent.py
|  `- summary_agent.py
|- services/
|  `- gemini_vision_service.py
|- ml/
|  |- urgency_model.py
|  |- model.pkl
|  `- encoders.pkl
|- rag/
|  |- retrieve_context.py
|  |- build_documents.py
|  |- process_symcat.py
|  `- build_index.py
|- data/
|  |- symcat_documents.json
|  |- symcat-474-symptoms.csv
|  `- symcat-801-diseases.csv
|- chat_controller.py
|- app_streamlit.py
`- requirements.txt
```

## How It Works (Pipeline)

1. **Intake Start**: capture age/gender and chief complaint.
2. **Guided Questions**: generate 3-5 follow-up questions from complaint + retrieval context.
3. **Clinical Synthesis**: convert conversation into structured NLICE JSON.
4. **Urgency Classification**: run ML model on NLICE features.
5. **Clinical Context + Summary**: produce a non-diagnostic report for clinician review.

## Setup

### 1. Clone repository

```bash
git clone https://github.com/Deborina-Barman/agentic-healthcare-ai.git
cd agentic-healthcare-ai
```

### 2. Create and activate virtual environment

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in project root:

```env
GEMINI_API_KEY=your_api_key_here
```

## Run the App

```bash
streamlit run app_streamlit.py
```

Then open the local Streamlit URL shown in terminal (usually `http://localhost:8501`).

## ML Model Notes

This repo already includes trained artifacts:

- `ml/model.pkl`
- `ml/encoders.pkl`

If you want to retrain:

```bash
python ml/urgency_model.py
```

## RAG Data Notes

The app currently uses lightweight TF-IDF retrieval from `data/symcat_documents.json` via `rag/retrieve_context.py`.

Optional FAISS index builder scripts are available under `rag/` if you want to extend retrieval.

## Important Safety Disclaimer

This project is for **educational and research purposes only**.

- It is **not** a medical device.
- It does **not** provide diagnosis or treatment advice.
- Outputs must be reviewed by qualified healthcare professionals.
- In emergencies, users should contact emergency services immediately.

## Future Improvements

- Add robust automated test coverage for the current chat pipeline.
- Add Docker support for one-command deployment.
- Add authentication, audit logs, and secure data storage for production use.
- Improve evaluation metrics for question quality and summary consistency.

## Author

Deborina Barman
