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
사용자의 증상을 파악하고 다음 세 가지 중 하나를 권장해 주세요:
1. EMERGENCY - 119에 전화하거나 즉시 응급실로 가세요
2. VISIT_HOSPITAL - 24시간 이내에 병원을 방문하세요
3. HOME_CARE - 집에서 쉬면서 경과를 지켜보세요

규칙:
- 공감하며 증상을 파악하기 위한 질문을 하세요
- 절대 진단하거나 약을 처방하지 마세요
- 항상 "저는 의료 전문가가 아닙니다. 이것은 진단이 아닙니다."라는 면책을 포함하세요
- 응급 키워드가 감지되면 즉시 EMERGENCY를 권장하세요
- 응답은 간결하고 명확하게 (한 번에 3문장 이내)
- 충분한 정보를 얻어 분류 권장을 할 수 있을 때, 응답 마지막에 다음을 추가하세요:
  TRIAGE: <EMERGENCY|VISIT_HOSPITAL|HOME_CARE>
- 병원 추천을 요청받으면, 증상을 먼저 파악한 후 VISIT_HOSPITAL을 권장하세요
"""

_OUTPUT_LANGUAGE_INSTRUCTION = {
    "ko": "반드시 한국어로 답변하세요.",
    "en": "Always respond in English.",
}


def build_triage_messages(
    history: list[dict],
    user_message: str,
    context: list[str] | None = None,
    language: str = "ko",
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


def parse_triage_result(reply: str) -> TriageResult | None:
    if "TRIAGE: EMERGENCY" in reply:
        return TriageResult.EMERGENCY
    if "TRIAGE: VISIT_HOSPITAL" in reply:
        return TriageResult.VISIT_HOSPITAL
    if "TRIAGE: HOME_CARE" in reply:
        return TriageResult.HOME_CARE
    return None


# Strip the machine-readable "TRIAGE: <LEVEL>" tag (and trailing whitespace) so it
# never leaks into the user-facing reply text or TTS audio.
_TRIAGE_TAG_RE = re.compile(
    r"\s*TRIAGE:\s*(EMERGENCY|VISIT_HOSPITAL|HOME_CARE)\s*", re.IGNORECASE
)


def clean_reply(reply: str) -> str:
    """Remove the TRIAGE meta tag from a reply for display/TTS."""
    return _TRIAGE_TAG_RE.sub(" ", reply).strip()
