import pytest

from app.triage.engine import (
    check_emergency_keywords,
    clean_reply_for_tts,
    extract_quick_reply_options,
    parse_triage_result,
)


class TestEmergencyKeywords:
    def test_detects_chest_pain(self):
        result = check_emergency_keywords("I have chest pain and dizziness")
        assert "chest pain" in result

    def test_detects_multiple_keywords(self):
        result = check_emergency_keywords("Patient is unconscious and not breathing")
        assert "unconscious" in result
        assert "not breathing" in result

    def test_no_keywords(self):
        result = check_emergency_keywords("I have a mild headache")
        assert result == []

    def test_case_insensitive(self):
        result = check_emergency_keywords("CHEST PAIN is severe")
        assert "chest pain" in result

    def test_suicide_detection(self):
        result = check_emergency_keywords("I feel suicidal")
        assert "suicidal" in result

    def test_overdose_detection(self):
        result = check_emergency_keywords("accidental overdose of medication")
        assert "overdose" in result


class TestParseTriageResult:
    def test_parse_emergency(self):
        reply = (
            "Based on symptoms...\n"
            "TRIAGE: EMERGENCY\n"
            "EXPLANATION: Severe chest pain with breathing difficulty\n"
            "NEXT_STEPS: Call 911, Go to ER immediately"
        )
        result = parse_triage_result(reply)
        assert result is not None
        assert result["level"] == "EMERGENCY"
        assert result["explanation"] == "Severe chest pain with breathing difficulty"
        assert len(result["next_steps"]) == 2

    def test_parse_visit_hospital(self):
        reply = (
            "TRIAGE: VISIT_HOSPITAL\n"
            "EXPLANATION: Persistent fever for 3 days\n"
            "NEXT_STEPS: Visit clinic within 24h, Monitor temperature"
        )
        result = parse_triage_result(reply)
        assert result["level"] == "VISIT_HOSPITAL"

    def test_parse_home_care(self):
        reply = (
            "TRIAGE: HOME_CARE\n"
            "EXPLANATION: Mild cold symptoms\n"
            "NEXT_STEPS: Rest, Stay hydrated, Monitor for 48 hours"
        )
        result = parse_triage_result(reply)
        assert result["level"] == "HOME_CARE"
        assert len(result["next_steps"]) == 3

    def test_no_triage_in_reply(self):
        reply = "Can you tell me more about your symptoms?"
        result = parse_triage_result(reply)
        assert result is None


class TestExtractQuickReplyOptions:
    def test_extracts_options(self):
        reply = 'How long have you had this? OPTIONS: ["Less than 1 hour", "1-6 hours", "More than 6 hours"]'
        options = extract_quick_reply_options(reply)
        assert options is not None
        assert len(options) == 3
        assert "Less than 1 hour" in options

    def test_no_options(self):
        reply = "Tell me more about your symptoms."
        options = extract_quick_reply_options(reply)
        assert options is None


class TestCleanReplyForTts:
    def test_removes_triage_tags(self):
        reply = (
            "You should rest at home.\n"
            "TRIAGE: HOME_CARE\n"
            "EXPLANATION: Mild symptoms\n"
            "NEXT_STEPS: Rest, Hydrate"
        )
        cleaned = clean_reply_for_tts(reply)
        assert "TRIAGE" not in cleaned
        assert "EXPLANATION" not in cleaned
        assert "NEXT_STEPS" not in cleaned
        assert "rest at home" in cleaned

    def test_removes_options(self):
        reply = 'Where does it hurt? OPTIONS: ["Head", "Chest", "Abdomen"]'
        cleaned = clean_reply_for_tts(reply)
        assert "OPTIONS" not in cleaned
        assert "Where does it hurt?" in cleaned
