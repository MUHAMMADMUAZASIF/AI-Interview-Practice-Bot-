from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

InterviewType = Literal["technical", "hr", "mixed"]
Difficulty = Literal["junior", "mid", "senior"]


class SessionConfig(BaseModel):
    role: str = Field(..., min_length=2, max_length=100, examples=["Backend Engineer"])
    interview_type: InterviewType = "technical"
    difficulty: Difficulty = "mid"
    num_questions: int = Field(5, ge=3, le=10)
    focus_areas: Optional[str] = Field(None, max_length=200, description="e.g. Python, system design")


class Evaluation(BaseModel):
    score: int = Field(..., ge=1, le=10)
    criteria: Dict[str, int] = {}
    strengths: List[str] = []
    improvements: List[str] = []
    ideal_answer: str = ""


class Turn(BaseModel):
    question: str
    topic: str = ""
    answer: Optional[str] = None
    evaluation: Optional[Evaluation] = None


class Session(BaseModel):
    id: str
    config: SessionConfig
    turns: List[Turn] = []
    finished: bool = False
    summary: Optional[dict] = None


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=5000)


class AnswerResponse(BaseModel):
    evaluation: Evaluation
    next_question: Optional[str] = None
    question_number: int
    finished: bool


class StartResponse(BaseModel):
    session_id: str
    question: str
    question_number: int
    total_questions: int
