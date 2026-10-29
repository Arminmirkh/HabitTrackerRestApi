"""
AI-assisted habit generation.

Uses Groq's chat completion API to turn a free-text goal into a
structured list of suggested habits. The API key is read from the
GROQ_API_KEY environment variable (see settings.py) -- it is never
hardcoded here.
"""
import json
import logging

from django.conf import settings
from groq import Groq

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-20b"

VALID_FREQUENCIES = {"daily", "weekly", "monthly"}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


class AIHabitGenerationError(Exception):
    """Raised when the AI response can't be obtained or parsed."""


def _get_client() -> Groq:
    if not settings.GROQ_API_KEY:
        raise AIHabitGenerationError(
            "GROQ_API_KEY is not configured. Set it as an environment variable."
        )
    return Groq(api_key=settings.GROQ_API_KEY)


def _build_prompt(goal: str) -> str:
    return f"""You are an expert habit-formation coach who applies behavioral
science (start small, be specific, tie new habits to existing routines,
make the first step nearly effortless).

The user's goal is:
"{goal}"

Generate 3  concrete habits that will help the user achieve this goal. one of each difficulty.

Rules for each habit:
- It must be a small, specific, repeatable action -- not vague advice
  (e.g. "Walk 20 minutes after lunch", not "Exercise more").
- "frequency" must be exactly one of: "daily", "weekly", "monthly".
- "difficulty" must be exactly one of: "easy", "medium", "hard".
- "title" must be a short action phrase, under 60 characters.
- "reason" must be 1-2 sentences explaining why this habit helps reach the goal.
- Order the habits from easiest to hardest.

Respond with ONLY valid JSON and nothing else -- no markdown, no code
fences, no commentary before or after -- it has to be 3 words or less -- matching exactly this schema:

{{
  "goal": "<goal restated in one concise sentence>",
  "habits": [
    {{
      "title": "<string>",
      "frequency": "daily|weekly|monthly",
      "difficulty": "easy|medium|hard",
      "reason": "<string>"
    }}
  ]
}}"""


def generate_habits(goal: str) -> dict:
    """
    Call the AI model and return a dict shaped like:
    {"goal": str, "habits": [{"title", "frequency", "difficulty", "reason"}, ...]}

    Raises AIHabitGenerationError on any failure (network, bad key,
    malformed response, etc).
    """
    client = _get_client()
    prompt = _build_prompt(goal)

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful habit coach that replies only in valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        logger.exception("Groq API call failed")
        raise AIHabitGenerationError(f"AI request failed: {exc}") from exc

    text = response.choices[0].message.content

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("AI returned invalid JSON: %s", text)
        raise AIHabitGenerationError("AI returned malformed JSON.") from exc

    habits = data.get("habits")
    if not isinstance(habits, list) or not habits:
        raise AIHabitGenerationError("AI response did not contain a habit list.")

    cleaned = []
    for h in habits:
        if not isinstance(h, dict) or not h.get("title"):
            continue
        frequency = h.get("frequency") if h.get("frequency") in VALID_FREQUENCIES else "daily"
        difficulty = h.get("difficulty") if h.get("difficulty") in VALID_DIFFICULTIES else "medium"
        cleaned.append({
            "title": str(h["title"])[:150],
            "frequency": frequency,
            "difficulty": difficulty,
            "reason": str(h.get("reason", ""))[:1000],
        })

    if not cleaned:
        raise AIHabitGenerationError("AI response contained no usable habits.")

    return {"goal": data.get("goal", goal), "habits": cleaned}
