import uuid
from dotenv import load_dotenv

# Load environment variables (.env) before importing modules that depend on API keys
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import llm, store
from .models import (AnswerRequest, AnswerResponse, Session, SessionConfig,
                    StartResponse, Turn)

app = FastAPI(title="AI Interview Practice Bot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _load(session_id: str) -> Session:
    try:
        session = store.get(session_id)
    except KeyError:
        session = None
    if not session:
        raise HTTPException(404, "Session not found")
    return session


@app.get("/health")
def health():
    return {"status": "ok", "model": llm.MODEL}


@app.post("/sessions", response_model=StartResponse)
def start_session(config: SessionConfig):
    session = Session(id=str(uuid.uuid4()), config=config)
    try:
        q = llm.generate_question(config, [])
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}")
    session.turns.append(Turn(question=q["question"], topic=q["topic"]))
    store.save(session)
    return StartResponse(
        session_id=session.id, question=q["question"],
        question_number=1, total_questions=config.num_questions,
    )


@app.post("/sessions/{session_id}/answer", response_model=AnswerResponse)
def submit_answer(session_id: str, body: AnswerRequest):
    session = _load(session_id)
    if session.finished:
        raise HTTPException(409, "Interview already finished")
    turn = session.turns[-1]
    if turn.answer is not None:
        raise HTTPException(409, "Current question already answered")

    try:
        turn.answer = body.answer.strip()
        turn.evaluation = llm.evaluate_answer(session.config, turn.question, turn.answer)
        finished = len(session.turns) >= session.config.num_questions
        next_q = None
        if finished:
            session.finished = True
        else:
            q = llm.generate_question(session.config, session.turns)
            session.turns.append(Turn(question=q["question"], topic=q["topic"]))
            next_q = q["question"]
    except Exception as e:
        turn.answer, turn.evaluation = None, None  # roll back so user can retry
        raise HTTPException(502, f"LLM error: {e}")

    store.save(session)
    return AnswerResponse(
        evaluation=turn.evaluation, next_question=next_q,
        question_number=len(session.turns), finished=finished,
    )


@app.post("/sessions/{session_id}/summary")
def get_summary(session_id: str):
    session = _load(session_id)
    answered = [t for t in session.turns if t.evaluation]
    if not session.finished or not answered:
        raise HTTPException(409, "Finish the interview before requesting a summary")
    if not session.summary:
        try:
            session.summary = llm.generate_summary(session.config, answered)
        except Exception as e:
            raise HTTPException(502, f"LLM error: {e}")
        store.save(session)
    return session.summary


@app.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: str):
    return _load(session_id)