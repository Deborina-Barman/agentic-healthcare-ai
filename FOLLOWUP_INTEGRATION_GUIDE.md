# Integration Guide: Retrieval-Augmented Clinical Question Generation

## Overview

This guide shows how to integrate the retrieval-augmented follow-up question system into your existing `chat_controller.py` workflow while maintaining deterministic orchestration.

**Key Principle**: Workflow orchestration stays in `chat_controller.py`. Gemini only improves question quality, not flow control.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│              chat_controller.py (Orchestrator)           │
│         [Deterministic Workflow Control]                 │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  extract_info_node()                                      │
│  • Parse user input                                       │
│  • Update NLICE state (nature, location, intensity, etc) │
│  • Return updated state                                   │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  question_node() [MODIFIED]                              │
│  • Check conversation completion (deterministic)         │
│  • Identify missing NLICE fields (deterministic)         │
│  • Get next field to ask about (deterministic)           │
│  • Decide: use structured question OR retrieve examples  │
└──────────────────────────────────────────────────────────┘
                            ↓
                    ┌───────┴───────┐
                    ↓               ↓
          ┌─────────────────┐  ┌──────────────────┐
          │ Structured Q    │  │ Complex symptom? │
          │ (if simple)     │  │ (if complex)     │
          └─────────────────┘  └──────────────────┘
                    ↓                   ↓
                            ┌───────────────────────┐
                            │ followup_retriever.py │
                            │ • Load FAISS index    │
                            │ • Embed complaint     │
                            │ • Retrieve top-k      │
                            │   clinician examples  │
                            └───────┬───────────────┘
                                    ↓
                    ┌───────────────────────────────────┐
                    │ followup_question_agent.py        │
                    │ • Build context-rich prompt       │
                    │ • Call Gemini 2.5 Flash          │
                    │ • Generate clinician-style Q      │
                    │ • Filter repeated questions       │
                    └───────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────┐
│  question_node() continues                               │
│  • Add question to state                                 │
│  • Return AIMessage                                      │
│  • Track in questions list                               │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│  [User responds]                                          │
│  [Loop back to extract_info_node]                         │
└──────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Integration

### Step 1: Import the New Agent in chat_controller.py

**Before** (current import):
```python
from agents.question_agent import (
    patient_question_agent,
)
```

**After** (add this import):
```python
from agents.question_agent import (
    patient_question_agent,
)
from agents.followup_question_agent import (
    followup_question_agent,
)
```

---

### Step 2: Modify the `question_node()` Function

**Original question_node** (around line 464 in chat_controller.py):

```python
def question_node(
    state: ClinicalState,
) -> dict:
    # ... existing code up to AI QUESTIONING section ...
    
    # ---------------------------------------------------
    # AI QUESTIONING
    # ---------------------------------------------------

    if (
        use_ai_questioning
         and not question
    ):
       
        try:

            result = patient_question_agent(
                complaint=complaint,
                age_gender=state.get(
                    "age_gender"
                ),
            )

            generated_questions = (
                result.get(
                    "questions",
                    [],
                )
            )
            
            # Avoid repeated questions
            previous_questions = [
                q.lower()
                for q in questions
            ]

            filtered_questions = []

            for q in generated_questions:

                if q.lower() not in previous_questions:

                    filtered_questions.append(q)

            generated_questions = filtered_questions

            if generated_questions:

                question = (
                    generated_questions[0]
                )

        except Exception as exc:

            print(
                "Question agent failed:",
                exc,
            )
```

**Replace the AI QUESTIONING section with**:

```python
    # ---------------------------------------------------
    # AI QUESTIONING (RETRIEVAL-AUGMENTED)
    # ---------------------------------------------------

    if (
        use_ai_questioning
         and not question
    ):
       
        try:
            # Prepare context for retrieval-augmented agent
            previous_questions = [
                q.lower()
                for q in questions
            ]
            
            # Call retrieval-augmented agent
            # (NEW - replaces patient_question_agent)
            result = followup_question_agent(
                complaint=complaint,
                nlice_state=state.get(
                    "nlice_data",
                    {},
                ),
                previous_questions=previous_questions,
                top_k=3,
            )

            if result.get("success"):
                # Generated question from retriever+Gemini
                question = result.get("question", "")
            else:
                # Fallback question from agent
                question = result.get("question", "")

        except Exception as exc:

            print(
                "Retrieval-augmented question agent failed:",
                exc,
            )
```

---

### Step 3: (Optional) Keep Legacy Fallback

If you want to maintain backwards compatibility with the old `patient_question_agent`:

```python
    # ---------------------------------------------------
    # AI QUESTIONING (RETRIEVAL-AUGMENTED)
    # ---------------------------------------------------

    if (
        use_ai_questioning
         and not question
    ):
       
        try:
            previous_questions = [
                q.lower()
                for q in questions
            ]
            
            # Try NEW retrieval-augmented approach first
            result = followup_question_agent(
                complaint=complaint,
                nlice_state=state.get(
                    "nlice_data",
                    {},
                ),
                previous_questions=previous_questions,
                top_k=3,
            )

            if result.get("success"):
                question = result.get("question", "")

            # If retrieval-augmented fails, fallback to legacy agent
            if not question:
                try:
                    legacy_result = patient_question_agent(
                        complaint=complaint,
                        age_gender=state.get(
                            "age_gender"
                        ),
                    )

                    generated_questions = (
                        legacy_result.get(
                            "questions",
                            [],
                        )
                    )
                    
                    filtered_questions = []

                    for q in generated_questions:

                        if q.lower() not in previous_questions:

                            filtered_questions.append(q)

                    if filtered_questions:

                        question = (
                            filtered_questions[0]
                        )

                except Exception as exc:
                    print(
                        "Legacy question agent fallback failed:",
                        exc,
                    )

        except Exception as exc:

            print(
                "Retrieval-augmented question agent failed:",
                exc,
            )
```

---

## Full Modified question_node() Example

Here's the complete modified function with all context:

```python
def question_node(
    state: ClinicalState,
) -> dict:
    """
    Generate the next follow-up question to fill NLICE gaps.
    
    Orchestration (deterministic):
    1. Check if conversation complete (max questions)
    2. Identify missing NLICE fields
    3. Use structured questions for critical fields
    4. Use retrieval-augmented agent for complex symptoms
    5. Avoid repeating previous questions
    """

    MAX_QUESTIONS = 5

    questions = list(
        state.get("questions") or []
    )

    # ---------------------------------------------------
    # LOOP PROTECTION (DETERMINISTIC)
    # ---------------------------------------------------

    if len(questions) >= MAX_QUESTIONS:

        return {

            "messages": [
                AIMessage(
                    content=(
                        "Clinical intake complete."
                    )
                )
            ],

            "conversation_complete": True,
        }

    # ---------------------------------------------------
    # IDENTIFY MISSING NLICE FIELDS (DETERMINISTIC)
    # ---------------------------------------------------

    missing_fields = _missing_nlice_fields(
        state.get("nlice_data")
    )

    next_field = (
        missing_fields[0]
        if missing_fields
        else None
    )

    if not next_field:
        return {}

    complaint = (
        state.get("complaint") or ""
    ).lower()

    # ---------------------------------------------------
    # STRUCTURED NLICE QUESTIONS (PRIORITY)
    # ---------------------------------------------------

    FIELD_QUESTION_MAP = {

        "nature":
            "Can you describe what the symptom feels like?",

        "location":
            "Where exactly are you feeling it?",

        "intensity":
            "How severe is it on a scale from 1 to 10?",

        "chronology":
            "When did it start?",

        "excitation":
            "Does anything make it better or worse?",
    }

    COMPLEX_SYMPTOMS = [

        "diarrhea",
        "vomiting",
        "chest pain",
        "difficulty breathing",
        "shortness of breath",
        "dizziness",
        "fatigue",
        "abdominal pain",
        "palpitations",
        "weakness",
        "fever",
    ]

    use_ai_questioning = any(
        symptom in complaint
        for symptom in COMPLEX_SYMPTOMS
    )

    question = ""

    # Structured NLICE fields always get priority
    if next_field in FIELD_QUESTION_MAP:

        question = FIELD_QUESTION_MAP[next_field]

    # ---------------------------------------------------
    # RETRIEVAL-AUGMENTED AI QUESTIONING
    # ---------------------------------------------------

    if (
        use_ai_questioning
         and not question
    ):
       
        try:
            # Prepare previous questions for deduplication
            previous_questions = [
                q.lower()
                for q in questions
            ]
            
            # Call retrieval-augmented agent
            result = followup_question_agent(
                complaint=complaint,
                nlice_state=state.get(
                    "nlice_data",
                    {},
                ),
                previous_questions=previous_questions,
                top_k=3,  # Retrieve top-3 similar examples
            )

            # Use generated question (from retriever + Gemini)
            # or fallback question (from agent's internal logic)
            if result.get("question"):
                question = result.get("question")

        except Exception as exc:

            print(
                "Retrieval-augmented question agent failed:",
                exc,
            )

    # ---------------------------------------------------
    # FINAL FALLBACK
    # ---------------------------------------------------

    if not question:

        question = FIELD_QUESTION_MAP.get(
            next_field,
            "Can you tell me more?",
        )

    # ---------------------------------------------------
    # UPDATE STATE
    # ---------------------------------------------------

    questions.append(question)

    return {

        "messages": [
            AIMessage(content=question)
        ],

        "questions": questions,

        "current_question_index": (
            len(questions) - 1
        ),
    }
```

---

## How Orchestration Remains Deterministic

### The Key: chat_controller.py Controls Flow, Not Gemini

| Aspect | Control | Decision |
|--------|---------|----------|
| **When to ask a question** | `question_node()` | Deterministic: checks missing NLICE fields |
| **Which field to ask about** | `_missing_nlice_fields()` | Deterministic: returns ordered list |
| **Structured vs AI** | `COMPLEX_SYMPTOMS` list | Deterministic: hardcoded symptom triggers |
| **Question repetition** | `previous_questions` list | Deterministic: explicit filtering |
| **Conversation termination** | `MAX_QUESTIONS` constant | Deterministic: hard limit |
| **Question quality/style** | Gemini + Retriever | **Non-deterministic**: Improves phrasing only |

**Gemini is confined to**: Improving question phrasing, adapting to retrieved examples, clinical style. **Not**: Deciding when to stop, what to ask about, whether to repeat.

---

## Testing the Integration

### Test in question_node() Directly

```python
# Quick test in Python REPL or test file
from chat_controller import question_node
from langchain_core.messages import HumanMessage

test_state = {
    "messages": [HumanMessage(content="sharp chest pain for 2 hours")],
    "complaint": "sharp chest pain for 2 hours",
    "nlice_data": {
        "nature": "sharp",
        "location": "chest",
        "intensity": "",
        "chronology": "2 hours",
        "excitation": "",
    },
    "questions": [],
}

result = question_node(test_state)
print(result["messages"][0].content)
```

### Test Standalone Agent

```bash
# Run the agent's test block directly
python agents/followup_question_agent.py
```

### Test Retriever Independently

```bash
# Test the retriever's FAISS search
python followup_retriever.py
```

---

## Performance Considerations

### Caching

Both modules use **lazy-loading** and **global caching** to optimize repeated calls:

```python
# In followup_retriever.py
_index = None      # Cached globally
_records = None    # Cached globally
_model = None      # Cached globally

# These are loaded once on first call, then reused
```

**Impact**: First question generation ~1-2 seconds (model load). Subsequent calls ~100-200ms (cached).

### Optimization Tips

1. **Preload resources** at app startup:
   ```python
   # In your app initialization
   from followup_retriever import retrieve_followup_examples
   
   # Warm up caches
   retrieve_followup_examples("warm up")
   ```

2. **Adjust top_k** for speed vs quality:
   ```python
   # Faster: retrieve fewer examples
   result = followup_question_agent(
       complaint=complaint,
       top_k=2,  # Instead of 3
   )
   ```

3. **Use Gemini caching** for identical complaints:
   - The agent is designed to handle this via Gemini's request caching

---

## Error Handling Strategy

The system has **three levels of fallback**:

```
Level 1: Retrieval-Augmented Agent
  ↓ (failure)
Level 2: Fallback questions in agent
  ↓ (failure)
Level 3: Structured NLICE map in question_node
  ↓ (failure)
Level 4: Generic fallback
```

Each level degrades gracefully:

```python
# Level 1: Retrieval-augmented (ideal)
result = followup_question_agent(...)
if result["success"]:
    question = result["question"]  # Quality question

# Level 2: Agent internal fallback (acceptable)
else:
    question = result["question"]  # Basic question

# Level 3: question_node fallback (minimal)
if not question:
    question = FIELD_QUESTION_MAP.get(next_field, "...")
```

---

## Debugging

### Enable Verbose Output

```python
# Add to chat_controller.py imports
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Then in question_node():
logger.debug(f"Missing fields: {missing_fields}")
logger.debug(f"Using next field: {next_field}")
logger.debug(f"Retrieval-augmented? {use_ai_questioning}")
logger.debug(f"Generated question: {question}")
```

### Check Retriever Health

```python
from followup_retriever import get_retriever_stats

stats = get_retriever_stats()
print(f"Index loaded: {stats['index_loaded']}")
print(f"Records: {stats['records_count']}")
print(f"Model: {stats['model_name']}")
```

---

## What NOT to Do

❌ **DON'T**: Move orchestration logic into Gemini
```python
# WRONG: Asking Gemini to decide workflow
prompt = "Based on the patient's complaint, what should we ask next?"
```

❌ **DON'T**: Skip the NLICE structured questions
```python
# WRONG: Always use retrieval-augmented
question = followup_question_agent(...)
```

✅ **DO**: Keep structured questions for critical fields
```python
# RIGHT: Prioritize NLICE framework
if next_field in FIELD_QUESTION_MAP:
    question = FIELD_QUESTION_MAP[next_field]
elif use_ai_questioning:
    result = followup_question_agent(...)
```

✅ **DO**: Use the retriever for context, not control
```python
# RIGHT: Retriever improves quality only
result = followup_question_agent(
    complaint=complaint,
    nlice_state=state,
    previous_questions=questions,
)
question = result["question"]  # Use the output, don't ask "should we?
```

---

## Summary

| Component | Purpose | Integration |
|-----------|---------|-----------|
| **followup_retriever.py** | Semantic search of clinician examples | Called by followup_question_agent |
| **followup_question_agent.py** | Context-aware question generation | Replaces patient_question_agent in question_node |
| **question_node()** | Orchestration (deterministic) | Enhanced but flow control unchanged |
| **chat_controller.py** | Workflow orchestration | Unchanged except for agent swap |

The system is now **retrieval-augmented** while maintaining your **deterministic, orchestration-first architecture**.

---

## Next Steps

1. ✅ Copy `followup_retriever.py` to root directory
2. ✅ Copy `agents/followup_question_agent.py` to agents folder
3. ✅ Update imports in `chat_controller.py`
4. ✅ Replace the AI QUESTIONING section in `question_node()`
5. ✅ Test with the standalone test blocks
6. ✅ Run full system test
