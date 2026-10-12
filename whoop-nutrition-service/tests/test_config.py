import pytest

from services.nutrition.config import NutritionSettings


def test_unpriced_llm_model_is_rejected_at_construction():
    with pytest.raises(ValueError, match="PRICE_PER_MTOK_USD"):
        NutritionSettings(anthropic_api_key="key", llm_model="gpt-4o")


def test_unpriced_transcription_model_is_rejected_at_construction():
    with pytest.raises(ValueError, match="WHISPER_PRICE_PER_MINUTE_USD"):
        NutritionSettings(anthropic_api_key="key", transcription_model="gpt-4o-transcribe")


def test_default_settings_construct_cleanly():
    settings = NutritionSettings(anthropic_api_key="key")
    assert settings.llm_model == "claude-sonnet-5"
    assert settings.transcription_model == "whisper-1"
