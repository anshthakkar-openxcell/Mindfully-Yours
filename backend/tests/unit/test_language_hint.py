from app.pipeline.language_hint import detect_language_style, language_instruction


def test_english_stays_english_even_with_ambiguous_words():
    assert detect_language_style("I just moved to a new city and my main worry is making friends") == "en"
    assert detect_language_style("Yes please, that would be nice.") == "en"
    assert detect_language_style("I want to quit smoking but I keep relapsing") == "en"


def test_devanagari_is_hindi():
    assert detect_language_style("मुझे हर चीज़ की चिंता रहती है") == "hi"


def test_romanised_hindi_and_mixed_messages_are_not_english():
    assert detect_language_style("mujhe marne ka mann kar raha hai, ab aur jeena nahi chahta") == "hinglish"
    assert detect_language_style("I got laid off yesterday aur mujhe lag raha hai ki main failure hoon") == "hinglish"
    assert detect_language_style("kya karu") == "hinglish"  # very short, one clear marker


def test_instruction_matches_style():
    assert "English only" in language_instruction("en")
    assert "Hinglish" in language_instruction("hinglish") and "SAME script" in language_instruction("hi")
