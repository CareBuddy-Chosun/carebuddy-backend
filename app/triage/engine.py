import json
import logging
import re
from enum import Enum

logger = logging.getLogger(__name__)

EMERGENCY_KEYWORDS = [
    # Korean
    "숨을 못", "숨이 안", "호흡곤란",
    "가슴 통증", "가슴이 아", "가슴 아파", "가슴이 답답", "가슴이 너무", "가슴이 쥐어",
    "심장마비", "뇌졸중", "의식 잃", "의식이 없", "기절",
    "경련", "발작", "대량 출혈", "피가 안 멈", "질식",
    "쓰러졌", "의식불명", "심정지",
    # English (keep for bilingual support)
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


def detect_language(text: str) -> str:
    """Return "ko" if any Hangul syllable is present, else "en"."""
    return "ko" if any("가" <= ch <= "힣" for ch in text) else "en"


async def translate_to_english(client, model: str, text: str) -> str:
    """Translate ``text`` to English via the LLM.

    Returns the original text unchanged on any error (graceful degradation).
    """
    if not text or not text.strip():
        return text
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Translate the user's message to English. "
                        "Output ONLY the translation, no quotes, no explanation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0,
            max_tokens=300,
        )
        translated = (response.choices[0].message.content or "").strip()
        return translated or text
    except Exception:  # noqa: BLE001
        logger.exception("Translation to English failed; using original text.")
        return text


TRIAGE_SYSTEM_PROMPT = """당신은 CareBuddy, 음성 기반 AI 의료 분류 도우미입니다.
사용자의 증상을 공감하며 충분히 파악하는 것이 목표입니다.

다음 다섯 가지 정보를 모으세요:
1) 주요 증상과 부위
2) 발병 시점과 지속 기간
3) 심한 정도
4) 동반 증상
5) 기저질환·복용 중인 약

대화 방식:
- 한 번에 하나씩, 공감하는 태도로 빠진 정보를 묻는 후속 질문을 하세요.
- 사용자가 한 번에 여러 정보를 주면 중복해서 묻지 말고, 아직 빠진 항목만 물으세요.
- 절대 진단하거나 약을 처방하지 마세요.
- 응답은 짧고 명확하게 (3문장 이내).
- 분류 결과(응급/병원/자가)와 면책 안내는 시스템이 자동으로 처리합니다. 당신은
  분류 결과나 면책 문구를 직접 말하지 말고, 자연스러운 증상 파악 대화에만 집중하세요.
"""

# A separate structured pass decides whether enough has been collected and which
# triage level applies. The conversational model above is unreliable at emitting
# machine tags inline, so we don't depend on it for classification.
_ASSESSMENT_SYSTEM_PROMPT = """You analyze a medical triage conversation (which may be in Korean) and report what has been collected so far.
Respond with ONLY a JSON object, no other text:
{"main": bool, "onset": bool, "severity": bool, "assoc": bool, "history": bool, "triage": "EMERGENCY" | "VISIT_HOSPITAL" | "HOME_CARE" | null}

Field meaning (true only if clearly established in the conversation):
- main: the chief symptom and its body location are known
- onset: when it started and/or how long it has lasted is known
- severity: how severe/intense it is is known
- assoc: associated symptoms (or their clear absence) are known
- history: underlying conditions / current medications (or their clear absence) are known

triage: set ONLY when all five fields are true; otherwise null. When set, classify by urgency:
- EMERGENCY: life-threatening signs (severe chest pain, breathing difficulty, altered consciousness, etc.)
- VISIT_HOSPITAL: should be seen by a clinician within ~24h
- HOME_CARE: mild, can be observed at home
"""


def format_conversation(
    history: list[dict], current_user: str, current_assistant: str = ""
) -> str:
    """Render the dialogue as plain text for the assessment pass.

    ``current_assistant`` is optional so we can assess what the patient has
    provided before the assistant's next reply exists.
    """
    lines = []
    for m in history:
        who = "Patient" if m["role"] == "user" else "Assistant"
        lines.append(f"{who}: {m['content']}")
    lines.append(f"Patient: {current_user}")
    if current_assistant:
        lines.append(f"Assistant: {current_assistant}")
    return "\n".join(lines)


def _parse_assessment(raw: str) -> dict | None:
    """Extract {"slots": {...}, "triage": TriageResult|None} from model JSON."""
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    slots = {slot: bool(data.get(slot)) for slot in REQUIRED_SLOTS}
    level = None
    triage = data.get("triage")
    if isinstance(triage, str) and triage.strip().lower() in (
        "emergency",
        "visit_hospital",
        "home_care",
    ):
        level = TriageResult(triage.strip().lower())
    return {"slots": slots, "triage": level}


# Korean medical departments the recommender may choose from. Used both to
# constrain the model and as Naver search keywords for nearby clinics.
MEDICAL_DEPARTMENTS = (
    "내과",
    "외과",
    "정형외과",
    "신경과",
    "신경외과",
    "이비인후과",
    "안과",
    "피부과",
    "비뇨의학과",
    "산부인과",
    "소아청소년과",
    "정신건강의학과",
    "가정의학과",
    "재활의학과",
    "치과",
    "한의원",
)
_DEFAULT_DEPARTMENT = "가정의학과"

_CARE_SYSTEM_PROMPT = (
    "You map a medical condition and a patient's symptoms to (a) the condition's "
    "Korean name and (b) the single most appropriate Korean medical department to "
    "visit. Respond with ONLY a JSON object:\n"
    '{"condition_ko": "<the condition name in Korean>", "department": "<one department>"}\n'
    "The department MUST be exactly one of: " + ", ".join(MEDICAL_DEPARTMENTS) + ".\n"
    "Pick the single best fit; if unsure use 가정의학과."
)


async def recommend_care(
    client, model: str, condition: str, symptoms: str
) -> dict | None:
    """Return {"condition_ko": str, "department": str} for a condition+symptoms.

    ``department`` is always one of MEDICAL_DEPARTMENTS (Naver-searchable). Falls
    back to the default department on any error. Returns None only if unusable.
    """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _CARE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Condition: {condition}\nSymptoms: {symptoms}",
                },
            ],
            temperature=0,
            max_tokens=120,
        )
        raw = response.choices[0].message.content or ""
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
        dept = (data.get("department") or "").strip()
        if dept not in MEDICAL_DEPARTMENTS:
            dept = _DEFAULT_DEPARTMENT
        condition_ko = (data.get("condition_ko") or "").strip() or condition
        return {"condition_ko": condition_ko, "department": dept}
    except (ValueError, TypeError):
        return {"condition_ko": condition, "department": _DEFAULT_DEPARTMENT}
    except Exception:  # noqa: BLE001
        logger.exception("Care recommendation failed.")
        return None


async def assess_conversation(client, model: str, conversation_text: str) -> dict | None:
    """Structured slot/triage assessment of the conversation.

    Returns {"slots": {slot: bool}, "triage": TriageResult|None}, or None on error.
    """
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _ASSESSMENT_SYSTEM_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            temperature=0,
            max_tokens=150,
        )
        return _parse_assessment(response.choices[0].message.content or "")
    except Exception:  # noqa: BLE001
        logger.exception("Symptom assessment failed.")
        return None

_OUTPUT_LANGUAGE_INSTRUCTION = {
    "ko": "반드시 한국어로 답변하세요.",
    "en": "Always respond in English.",
}


def build_triage_messages(
    history: list[dict],
    user_message: str,
    context: list[str] | None = None,
    language: str = "ko",
    directive: str | None = None,
) -> list[dict]:
    messages = [{"role": "system", "content": TRIAGE_SYSTEM_PROMPT}]
    if context:
        joined = "\n\n---\n\n".join(context)
        messages.append(
            {
                "role": "system",
                "content": (
                    "다음은 참고용 의료 정보입니다. "
                    "진단이 아니라 분류 판단에만 활용하세요:\n\n" + joined
                ),
            }
        )
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    # A turn-specific instruction (ask about a missing slot, or close out) so the
    # system — not the model's whim — drives what happens next.
    if directive:
        messages.append({"role": "system", "content": directive})
    # Force the output language dynamically (placed last for strongest effect).
    messages.append(
        {
            "role": "system",
            "content": _OUTPUT_LANGUAGE_INSTRUCTION.get(
                language, _OUTPUT_LANGUAGE_INSTRUCTION["ko"]
            ),
        }
    )
    return messages


# Per-slot prompts the system uses to drive the next question, plus templated
# fallbacks used verbatim if the model returns an empty reply.
SLOT_TOPICS = {
    "ko": {
        "main": "어떤 증상이 몸의 어느 부위에 있는지",
        "onset": "증상이 언제부터 시작됐고 얼마나 지속되는지",
        "severity": "통증·불편함의 정도를 1~10 숫자로(1=아주 약함, 5=보통, 10=견디기 힘들 만큼 극심함) 몇 점인지",
        "assoc": "함께 나타나는 다른 증상이 있는지",
        "history": "기저질환이나 현재 복용 중인 약이 있는지",
    },
    "en": {
        "main": "what the main symptom is and where in the body it is",
        "onset": "when the symptom started and how long it has lasted",
        "severity": "how severe it is on a 1-10 scale (1 = very mild, 5 = moderate, 10 = unbearable)",
        "assoc": "whether there are any other accompanying symptoms",
        "history": "any underlying conditions or current medications",
    },
}

SLOT_FALLBACK_QUESTION = {
    "ko": {
        "main": "어떤 증상이 몸의 어느 부위에 있는지 좀 더 자세히 알려주시겠어요?",
        "onset": "증상이 언제부터 시작됐고 얼마나 지속되고 있나요?",
        "severity": "통증이나 불편함이 1~10 중 몇 점 정도인가요? (1: 아주 약함, 5: 보통, 10: 견디기 힘들 만큼 극심함)",
        "assoc": "그 외에 함께 나타나는 증상이 있나요?",
        "history": "기저질환이나 현재 복용 중인 약이 있나요?",
    },
    "en": {
        "main": "Could you tell me a bit more about what the symptom is and where it is?",
        "onset": "When did the symptom start, and how long has it lasted?",
        "severity": "On a scale of 1-10, how severe is it? (1 = very mild, 5 = moderate, 10 = unbearable)",
        "assoc": "Are there any other symptoms occurring alongside it?",
        "history": "Do you have any underlying conditions or take any medications?",
    },
}

_ASK_DIRECTIVE = {
    "ko": "다음 정보를 공감하는 말투로 한 문장으로 자연스럽게 물어보세요: {topic}. 다른 말은 최소화하세요.",
    "en": "Ask, in one empathetic sentence, about the following: {topic}. Keep it brief.",
}

_CLOSING_DIRECTIVE = {
    "ko": "지금까지 말씀하신 증상을 한 문장으로 공감하며 정리하고, 곧 분류 결과를 보여드리겠다고 안내하세요. 진단명이나 분류 단계는 직접 말하지 마세요.",
    "en": "In one empathetic sentence, summarize the symptoms described so far and say the triage result will be shown next. Do not state a diagnosis or the triage level yourself.",
}

_CLOSING_FALLBACK = {
    "ko": "말씀해 주신 증상을 바탕으로 분류 결과를 정리했어요.",
    "en": "Based on the symptoms you've shared, here is your triage result.",
}


def ask_directive(language: str, slot: str) -> str:
    lang = language if language in SLOT_TOPICS else "ko"
    topic = SLOT_TOPICS[lang].get(slot, SLOT_TOPICS[lang]["main"])
    return _ASK_DIRECTIVE[lang].format(topic=topic)


def fallback_question(language: str, slot: str) -> str:
    lang = language if language in SLOT_FALLBACK_QUESTION else "ko"
    return SLOT_FALLBACK_QUESTION[lang].get(slot, SLOT_FALLBACK_QUESTION[lang]["main"])


def closing_directive(language: str) -> str:
    return _CLOSING_DIRECTIVE.get(language, _CLOSING_DIRECTIVE["ko"])


def closing_fallback(language: str) -> str:
    return _CLOSING_FALLBACK.get(language, _CLOSING_FALLBACK["ko"])


def first_missing_slot(slots: dict[str, bool]) -> str | None:
    """Return the first required slot not yet filled, or None if all filled."""
    for slot in REQUIRED_SLOTS:
        if not slots.get(slot):
            return slot
    return None


_TRIAGE_PARSE_RE = re.compile(
    r"TRIAGE:\s*(EMERGENCY|VISIT_HOSPITAL|HOME_CARE)", re.IGNORECASE
)


def parse_triage_result(reply: str) -> TriageResult | None:
    m = _TRIAGE_PARSE_RE.search(reply)
    if not m:
        return None
    return TriageResult(m.group(1).lower())


# Required symptom slots the assistant must collect before a (non-emergency)
# triage is accepted. Mirrors the STATUS line in TRIAGE_SYSTEM_PROMPT.
REQUIRED_SLOTS = ("main", "onset", "severity", "assoc", "history")

# Match the known slot tokens anywhere (e.g. "main=Y", "onset = N"). Restricted
# to the known slot names so scanning free text can't false-positive.
_SLOT_RE = re.compile(
    r"\b(main|onset|severity|assoc|history)\s*=\s*([YN])\b", re.IGNORECASE
)


def parse_status(reply: str) -> dict[str, bool] | None:
    """Parse the model's slot self-report (e.g. "STATUS: main=Y onset=N ...").

    Tolerant of a missing "STATUS:" prefix — scans the whole reply for the
    known slot tokens. Returns a {slot: bool} map, or None if none are found.
    """
    pairs = _SLOT_RE.findall(reply)
    if not pairs:
        return None
    return {slot.lower(): val.upper() == "Y" for slot, val in pairs}


def all_required_slots_filled(status: dict[str, bool] | None) -> bool:
    """True only if every required slot is present and marked Y."""
    if not status:
        return False
    return all(status.get(slot, False) for slot in REQUIRED_SLOTS)


# Strip the machine-readable meta lines (TRIAGE / STATUS) so they never leak
# into the user-facing reply text or TTS audio.
_TRIAGE_TAG_RE = re.compile(
    r"\s*TRIAGE:\s*(EMERGENCY|VISIT_HOSPITAL|HOME_CARE)\s*", re.IGNORECASE
)
# A whole STATUS line (with optional markdown/bracket decoration), and — as a
# fallback when the model drops the "STATUS:" prefix — any run of bare slot
# tokens like "main=Y onset=N ...".
_STATUS_LINE_RE = re.compile(r"[ \t]*[\*_`\[\(]*\s*STATUS:[^\n\r]*", re.IGNORECASE)
_SLOT_TOKENS_RE = re.compile(
    r"(?:[ \t]*[\[\(\*_`]*\b(?:main|onset|severity|assoc|history)\s*=\s*[YN]\b"
    r"[\]\)\*_`,]*){1,}",
    re.IGNORECASE,
)


def clean_reply(reply: str) -> str:
    """Remove the TRIAGE and STATUS meta lines from a reply for display/TTS."""
    cleaned = _STATUS_LINE_RE.sub(" ", reply)
    cleaned = _SLOT_TOKENS_RE.sub(" ", cleaned)
    cleaned = _TRIAGE_TAG_RE.sub(" ", cleaned)
    # Tidy any leftover blank lines / double spaces from the removals.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", cleaned)
    return cleaned.strip()
