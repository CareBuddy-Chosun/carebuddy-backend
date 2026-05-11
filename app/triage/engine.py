import re
from enum import Enum

EMERGENCY_KEYWORDS = [
    "can't breathe", "cannot breathe", "difficulty breathing", "chest pain",
    "heart attack", "stroke", "unconscious", "fainting", "fainted",
    "seizure", "severe bleeding", "not breathing", "choking",
    "loss of consciousness", "unresponsive", "not responding",
    "overdose", "suicide", "suicidal", "passed out",
]

DISCLAIMER_TEXT = (
    "This is not a medical diagnosis. CareBuddy is a triage assistance tool only. "
    "Always consult a qualified healthcare professional for medical advice."
)


class TriageLevel(str, Enum):
    EMERGENCY = "EMERGENCY"
    VISIT_HOSPITAL = "VISIT_HOSPITAL"
    HOME_CARE = "HOME_CARE"


def check_emergency_keywords(text: str) -> list[str]:
    """Return list of matched emergency keywords."""
    text_lower = text.lower()
    return [kw for kw in EMERGENCY_KEYWORDS if kw in text_lower]


TRIAGE_SYSTEM_PROMPT = """You are CareBuddy, a voice-first AI healthcare triage assistant.
Your role is to help users assess their symptoms and recommend one of three actions:
1. EMERGENCY - Call 911 or go to the ER immediately
2. VISIT_HOSPITAL - See a doctor within 24 hours
3. HOME_CARE - Rest and monitor at home

Rules:
- Ask focused, empathetic questions to understand the symptom
- Never diagnose or prescribe medication
- Keep responses concise and clear (under 3 sentences per turn)
- Maximum 8 conversational turns before providing a recommendation
- When offering choices, format them as: OPTIONS: ["option1", "option2", "option3"]

When you have enough information to make a triage recommendation, end your response with a structured block:
TRIAGE: <EMERGENCY|VISIT_HOSPITAL|HOME_CARE>
EXPLANATION: <brief plain-language reasoning, max 150 words>
NEXT_STEPS: <comma-separated recommended actions>

Always include the disclaimer: "I am not a medical professional. This is not a diagnosis."
"""


def build_triage_messages(history: list[dict], user_message: str) -> list[dict]:
    messages = [{"role": "system", "content": TRIAGE_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def parse_triage_result(reply: str) -> dict | None:
    """Parse structured triage output from LLM reply.

    Returns dict with keys: level, explanation, next_steps, or None if no triage found.
    """
    level = None
    if "TRIAGE: EMERGENCY" in reply:
        level = TriageLevel.EMERGENCY
    elif "TRIAGE: VISIT_HOSPITAL" in reply:
        level = TriageLevel.VISIT_HOSPITAL
    elif "TRIAGE: HOME_CARE" in reply:
        level = TriageLevel.HOME_CARE

    if level is None:
        return None

    explanation = None
    explanation_match = re.search(r"EXPLANATION:\s*(.+?)(?=\nNEXT_STEPS:|$)", reply, re.DOTALL)
    if explanation_match:
        explanation = explanation_match.group(1).strip()

    next_steps = []
    steps_match = re.search(r"NEXT_STEPS:\s*(.+?)$", reply, re.DOTALL)
    if steps_match:
        raw = steps_match.group(1).strip()
        next_steps = [s.strip() for s in raw.split(",") if s.strip()]

    return {
        "level": level.value,
        "explanation": explanation,
        "next_steps": next_steps,
    }


def extract_quick_reply_options(reply: str) -> list[str] | None:
    """Extract OPTIONS: ["a", "b", "c"] from LLM reply."""
    match = re.search(r'OPTIONS:\s*\[(.+?)\]', reply)
    if not match:
        return None
    raw = match.group(1)
    options = [s.strip().strip('"').strip("'") for s in raw.split(",")]
    return options if options else None


def clean_reply_for_tts(reply: str) -> str:
    """Remove structured tags from reply for TTS output."""
    cleaned = re.sub(r"TRIAGE:.*$", "", reply, flags=re.MULTILINE | re.DOTALL)
    cleaned = re.sub(r"EXPLANATION:.*$", "", cleaned, flags=re.MULTILINE | re.DOTALL)
    cleaned = re.sub(r"NEXT_STEPS:.*$", "", cleaned, flags=re.MULTILINE | re.DOTALL)
    cleaned = re.sub(r"OPTIONS:\s*\[.*?\]", "", cleaned)
    return cleaned.strip()
