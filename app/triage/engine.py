from enum import Enum

EMERGENCY_KEYWORDS = [
    "can't breathe", "cannot breathe", "difficulty breathing", "chest pain",
    "heart attack", "stroke", "unconscious", "fainting", "fainted",
    "seizure", "severe bleeding", "not breathing", "choking",
    "loss of consciousness", "unresponsive",
]


class TriageResult(str, Enum):
    EMERGENCY = "emergency"
    VISIT_HOSPITAL = "visit_hospital"
    HOME_CARE = "home_care"


def check_emergency_keywords(text: str) -> bool:
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in EMERGENCY_KEYWORDS)


TRIAGE_SYSTEM_PROMPT = """You are CareBuddy, a voice-first AI healthcare triage assistant.
Your role is to help users assess their symptoms and recommend one of three actions:
1. EMERGENCY - Call 911 or go to the ER immediately
2. VISIT_HOSPITAL - See a doctor within 24 hours
3. HOME_CARE - Rest and monitor at home

Rules:
- Ask focused, empathetic questions to understand the symptom
- Never diagnose or prescribe medication
- Always include the disclaimer: "I am not a medical professional. This is not a diagnosis."
- If any emergency keywords are detected, immediately recommend EMERGENCY
- Keep responses concise and clear (under 3 sentences per turn)
- When you have enough information to make a triage recommendation, end your response with:
  TRIAGE: <EMERGENCY|VISIT_HOSPITAL|HOME_CARE>
"""


def build_triage_messages(history: list[dict], user_message: str) -> list[dict]:
    messages = [{"role": "system", "content": TRIAGE_SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return messages


def parse_triage_result(reply: str) -> TriageResult | None:
    if "TRIAGE: EMERGENCY" in reply:
        return TriageResult.EMERGENCY
    if "TRIAGE: VISIT_HOSPITAL" in reply:
        return TriageResult.VISIT_HOSPITAL
    if "TRIAGE: HOME_CARE" in reply:
        return TriageResult.HOME_CARE
    return None
