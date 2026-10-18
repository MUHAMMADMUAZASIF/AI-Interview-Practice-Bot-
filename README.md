# AI Interview Practice Bot

Mock technical / HR interviews with per-answer evaluation and a final performance report.

**Stack:** Python · FastAPI (backend) · Streamlit (frontend) · Anthropic API

## Architecture
```
Streamlit UI  --HTTP-->  FastAPI  -->  LLM (3 prompt stages)
 frontend/app.py        backend/main.py   1. generate_question  (adaptive, no repeats)
                        backend/store.py  2. evaluate_answer    (rubric + feedback, JSON)
                        (JSON on disk)    3. generate_summary   (cross-answer patterns)
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your ANTHROPIC_API_KEY
```

## Run (two terminals)
```bash
uvicorn backend.main:app --reload --port 8000     # API docs: http://localhost:8000/docs
streamlit run frontend/app.py                     # UI:       http://localhost:8501
```

## Test
```bash
pytest
```

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/sessions` | Start interview, returns first question |
| POST | `/sessions/{id}/answer` | Submit answer, get evaluation + next question |
| POST | `/sessions/{id}/summary` | Final report (after last answer) |
| GET | `/sessions/{id}` | Full session transcript |

## Prompt design notes
- Prompts are centralized in `backend/prompts.py`.
- Evaluation uses a 4-criterion rubric (relevance, depth, clarity, structure) and calibrated scoring.
- Candidate text is wrapped in `<answer>` tags and treated as data, which reduces prompt injection.
- JSON-only outputs are parsed defensively with one retry; scores are clamped server-side.
- The average score is computed in code, not by the LLM.

## Ideas to extend
Voice input (speech-to-text), resume upload to tailor questions, user accounts + progress history (SQLite/Postgres),
streaming responses, Docker/Render deployment, timer-based pressure mode.
