import json
import os
import re
from typing import List

from dotenv import load_dotenv
from openai import OpenAI

from . import prompts
from .models import Evaluation, SessionConfig, Turn

load_dotenv()

# Default to deepseek-chat if LLM_MODEL is not set in .env
MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        # DeepSeek uses an OpenAI-compatible SDK with a custom base_url
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
    return _client


def parse_json(text: str) -> dict:
    """Extract a JSON object/array from model output, tolerating code fences and stray text."""
    if not isinstance(text, str):
        raise ValueError("Model output must be a string")

    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.IGNORECASE).strip()
    decoder = json.JSONDecoder()

    for start_char in ("{", "["):
        start = cleaned.find(start_char)
        while start != -1:
            try:
                value, end = decoder.raw_decode(cleaned[start:])
                if value is not None:
                    return value
            except json.JSONDecodeError:
                pass
            start = cleaned.find(start_char, start + 1)

    raise ValueError("No JSON object found in model output")


def _call_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Calls DeepSeek chat completion requesting JSON format with fallback parsing."""
    last_err = None
    for _ in range(2):  # one retry on malformed output
        try:
            resp = _get_client().chat.completions.create(
                model=MODEL,
                max_tokens=max_tokens,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            text = resp.choices[0].message.content or ""
            return parse_json(text)
        except (ValueError, json.JSONDecodeError, Exception) as e:
            last_err = e

    raise RuntimeError(f"Model returned invalid JSON: {last_err}")


def _fmt(config: SessionConfig, template: str) -> str:
    focus = f"\nFocus areas: {config.focus_areas}." if config.focus_areas else ""
    return template.format(
        role=config.role,
        interview_type=config.interview_type,
        difficulty=config.difficulty,
        focus=focus,
    )


def _history(turns: List[Turn]) -> str:
    if not turns:
        return "(no questions asked yet)"
    lines = []
    for i, t in enumerate(turns, 1):
        score = t.evaluation.score if t.evaluation else "n/a"
        lines.append(f"{i}. [{t.topic}] Q: {t.question}\n   Score: {score}/10")
    return "\n".join(lines)


def generate_question(config: SessionConfig, turns: List[Turn]) -> dict:
    user = (
        f"Questions so far:\n{_history(turns)}\n\n"
        f"This is question {len(turns) + 1} of {config.num_questions}. Ask the next question."
    )
    data = _call_json(_fmt(config, prompts.QUESTION_SYSTEM), user, max_tokens=400)
    return {"question": data["question"].strip(), "topic": data.get("topic", "")}


def evaluate_answer(config: SessionConfig, question: str, answer: str) -> Evaluation:
    user = f"Question:\n{question}\n\nCandidate's answer:\n<answer>\n{answer}\n</answer>"
    data = _call_json(_fmt(config, prompts.EVALUATION_SYSTEM), user, max_tokens=900)
    data["score"] = max(1, min(10, int(data["score"])))
    data["criteria"] = {k: max(1, min(10, int(v))) for k, v in data.get("criteria", {}).items()}
    return Evaluation(**data)


def generate_summary(config: SessionConfig, turns: List[Turn]) -> dict:
    blocks = []
    for i, t in enumerate(turns, 1):
        ev = t.evaluation
        blocks.append(
            f"Q{i} [{t.topic}]: {t.question}\nAnswer: {t.answer}\n"
            f"Score: {ev.score}/10 | Criteria: {ev.criteria}\n"
            f"Strengths: {ev.strengths}\nImprovements: {ev.improvements}"
        )
    data = _call_json(_fmt(config, prompts.SUMMARY_SYSTEM), "\n\n".join(blocks), max_tokens=1500)
    scores = [t.evaluation.score for t in turns if t.evaluation]
    data["average_score"] = round(sum(scores) / len(scores), 1) if scores else 0
    return data