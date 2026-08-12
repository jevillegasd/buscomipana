from app.gateways.base import MAX_SMS_SEGMENT_CHARS, fit_single_sms, to_gsm7


def test_to_gsm7_transliterates_acute_vowels_not_in_gsm7_alphabet():
    # á í ó ú (and uppercase) have no GSM-7 representation at all, unlike
    # é/è/à/ñ/ü, which are natively in the GSM 03.38 default alphabet and are
    # left untouched.
    assert to_gsm7("ESTÁ BIEN, código número 5") == "ESTA BIEN, codigo numero 5"
    assert to_gsm7("Perú, José, ñoño, día") == "Peru, José, ñoño, dia"


def test_to_gsm7_transliterates_smart_punctuation():
    assert to_gsm7("“ok” – nos vemos…") == '"ok" - nos vemos...'


def test_to_gsm7_drops_unmappable_characters_like_emoji():
    # A stray character with no GSM-7 or transliteration mapping (e.g. an
    # emoji) must be dropped, not passed through -- letting it through would
    # force the whole message into UCS-2 and cut the segment budget to 70.
    assert to_gsm7("cuidado ⚠ zona de riesgo") == "cuidado  zona de riesgo"
    for ch in to_gsm7("emoji test 🚨🔥😀"):
        assert ch in " emojitest"


def test_fit_single_sms_hard_truncates_to_segment_budget():
    long_text = "a" * 200
    result = fit_single_sms(long_text)
    assert len(result) == MAX_SMS_SEGMENT_CHARS

    short_text = "short message"
    assert fit_single_sms(short_text) == short_text
