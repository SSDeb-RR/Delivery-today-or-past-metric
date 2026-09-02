
from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from delivery_scheduled_today_past import evaluate_delivery_scheduled_today_past


LOGS_SEP_2 = {"currentDate": "Wednesday, September 2, 2026"}


def text_transcript_to_turns(text):
    turns = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        role, sep, body = line.partition(":")
        if sep and role.strip().lower() in {"agent", "customer", "user", "assistant"}:
            normalized_role = "customer" if role.strip().lower() in {"customer", "user"} else "agent"
            turns.append({"role": normalized_role, "text": body.strip()})
    return {"turns": turns}


def test_historical_date_is_not_the_target():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 16 August."},
            {"role": "agent", "text": "We can schedule the delivery for tomorrow."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["transcript_today"] == "2000-08-16"
    assert result["historical_delivery_date"] == "2000-08-16"
    assert result["effective_new_schedule_date"] is None
    assert result["value"] == "false"


def test_new_schedule_today_is_true():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 26 August."},
            {"role": "agent", "text": "Your delivery is scheduled for today."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["transcript_today"] == "2000-08-26"
    assert result["effective_new_schedule_date"] == "2000-08-26"
    assert result["value"] == "true"


def test_new_schedule_past_is_true():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver your order on 26 August."},
            {"role": "agent", "text": "We have rescheduled your delivery for 22 August."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_new_schedule_date"] == "2000-08-22"
    assert result["value"] == "true"


def test_proposal_tomorrow_is_not_a_schedule():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can attempt the delivery again tomorrow."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["effective_new_schedule_date"] is None


def test_customer_request_does_not_become_agent_schedule():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "customer", "text": "Can you deliver it today?"},
            {"role": "agent", "text": "No, today is not possible. Tomorrow is the earliest."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["effective_new_schedule_date"] is None


def test_later_confirmed_effective_date_wins():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can deliver tomorrow."},
            {"role": "customer", "text": "No, please do 23 August."},
            {"role": "agent", "text": "Okay, your delivery is scheduled for 23 August."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_schedule_expression"] == "23 August"
    assert result["value"] == "false"


def test_next_week_sunday_proposal_is_not_a_schedule():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 16 August."},
            {"role": "agent", "text": "We can schedule it for next week Sunday."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["effective_new_schedule_date"] is None
    assert result["value"] == "false"


def test_no_anchor_is_false_and_auditable():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We can schedule your delivery for tomorrow."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["transcript_today"] is None


def test_mixed_historical_and_confirmed_date_uses_confirmed_date():
    transcript = {
        "turns": [
            {
                "role": "agent",
                "text": "The delivery failed on 16 August. Your delivery is scheduled for 18 August.",
            }
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "false"
    assert result["effective_new_schedule_date"] == "2000-08-18"


def test_confirmed_today_is_true():
    transcript = {
        "turns": [
            {"role": "agent", "text": "We were unable to deliver on 26 August."},
            {"role": "agent", "text": "Your delivery has been rescheduled for today."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript)
    assert result["value"] == "true"


def test_logs_current_date_is_authoritative():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 26 August."},
            {"role": "agent", "text": "Your delivery is scheduled for September 2."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript, logs=LOGS_SEP_2)
    assert result["transcript_today"] == "2026-09-02"
    assert result["effective_new_schedule_date"] == "2026-09-02"
    assert result["value"] == "true"


def test_log_current_date_falls_back_to_transcript_when_absent():
    transcript = {
        "turns": [
            {"role": "agent", "text": "The delivery failed on 26 August."},
            {"role": "agent", "text": "Your delivery is scheduled for 27 August."},
        ]
    }
    result = evaluate_delivery_scheduled_today_past(transcript, logs={})
    assert result["transcript_today"] == "2000-08-26"
    assert result["value"] == "false"


# The five newly supplied false-positive calls.
NEW_FALSE_POSITIVE_CASES = [
    {
        "id": "call_1_alfia",
        "transcript": """assistant: नमस्ते Alfia, मैं Sotru से Anika हूँ। आपकी delivery second September को attempt की गई थी लेकिन हम आपको नहीं पा सके। Delivery failure का कारण था कि आप उपलब्ध नहीं थे। क्या यह सही है?
user: क्यों?
assistant: मुझे खेद है कि delivery partner ने गलत जानकारी दी। मैं यह बात note कर लेती हूँ। आप cash on delivery के बारे में सही कह रही हैं। अब मैं आपकी delivery फिर से schedule करने में मदद करती हूँ। क्या कल delivery के लिए आपको ठीक रहेगा?
user: Hello, hello. Hello.
assistant: हमारी delivery service में सबसे जल्दी हम कल ही delivery फिर से कर सकते हैं। आज की तारीख में delivery schedule करना संभव नहीं है। क्या कल का दिन?
assistant: नमस्ते, मैं Anika Sotru से हूँ। मैं आपकी delivery के बारे में जानकारी लेने की कोशिश कर रही थी। मैं फिर से call करूंगी। धन्यवाद।
user: एएए""",
    },
    {
        "id": "call_2_kammam",
        "transcript": """assistant: Good morning, I am calling regarding your recent Neeman's order. Actually, we were unable to deliver your order on 2nd September. I am just calling to reschedule your delivery. Thank you. The delivery partner noted the reason
user: उम।
user: Okay.
assistant: reason--
user: Okay.
assistant: since you responded in Hindi, I will continue in Hindi for the rest of the call. धन्यवाद। Delivery partner ने बताया कि delivery fail होने का कारण था customer unavailable यानी आप उपलब्ध नहीं थे।
user: Okay.""",
    },
    {
        "id": "call_3_pranav",
        "transcript": """assistant: मैं PopClub से आपके recent order के बारे में call कर रही हूं। हम 2nd September को इसे deliver नहीं कर पाए और मैं इसे reschedule करना चाहती थी। बस थोड़ा better समझने के लिए।
user: ए
assistant: क्या हम-
assistant: माफ कीजिए, मैं वह ठीक से सुन नहीं पाई। क्या आप एक बार दोबारा कह सकते हैं?
user: Deliver हो गया था order.
assistant: अरे यह सुनकर अच्छा लगा। माफ कीजिए, हमारे system update में थोड़ी देरी हुई होगी। मुझे खुशी है कि order आप तक पहुंच गया। Confirm करने के लिए शुक्रिया। आपका दिन अच्छा हो।""",
    },
    {
        "id": "call_4_neeman",
        "transcript": """user: Hello
assistant: Hi
assistant: मैं Neeman से आपकी recent order के बारे में call कर रही हूँ। हम second September को इसे deliver नहीं कर पाए और मैं इसे reschedule करना चाहती थी। बस थोड़ा better समझने के लिए। क्या हमारे delivery partner ने आपका order deliver करने की कोशिश की थी या आपको उनसे-
user: उन्होंने की थी। मैंने बात भी की और मैंने उनको बोला कि आप order cancel कर दो क्योंकि मेरी Neeman से जो customer care थी उसमें बात ही नहीं हो पा रही थी।
user: आप पूरी तरह समझ ही नहीं सकते ना क्योंकि call अगर pickup होगा तभी तो मैं कुछ बोलूंगा।
assistant: मैं पूरी तरह समझ सकती हूँ कि आप क्यों upset हैं और-
assistant: मैं आपकी बात समझ रही हूँ और इस परेशानी के लिए मुझे सच में बहुत खेद है।
user: Okay. आपकी real में इतनी आवाज अच्छी है कि AI code है ऐसा कुछ है?
user: Okay.
assistant: जी हाँ, मैं Neeman's team की digital assistant हूँ। आपकी delivery reschedule करने में help करने के लिए। क्या हम continue करें?
user: हाँ, बोलिए।
user: Actually मेरे को order cancel करना है। अगर मैं आपको in short बोल दूँ तो।
user: मेरे को order cancel करना है।
assistant: मैं समझती हूँ।
assistant: बस confirm.
user: Hello आपका आवाज- You are not audible ma'am.
assistant: sorry.
assistant: I'm
assistant: Hi, this is Anika from Neeman's. I am calling about your recent order. I will try to reach you again later. Thank you.
user: Thank you.""",
    },
    {
        "id": "call_5_arya",
        "transcript": """assistant: आर्य जी, क्या आप अभी उपलब्ध हैं? मैं आपकी delivery reschedule करने में मदद कर सकती हूँ।
user: reschedule. तो आने वाला था।
assistant: धन्यवाद आर्य जी। आपकी delivery दूसरे सितंबर को delivery partner ने delivery attempt की थी, लेकिन वे आपको contact नहीं कर पाए थे।
user: आज
user: Extra charge नहीं कर दिया। पाँच को तो आप ने time-
assistant: आर्य जी, मैं समझती हूँ कि आपको confusion हुई है। Delivery attempt actually दो सितंबर को हुई थी और हम delivery को फिर से schedule कर सकते हैं। मैं extra charges के बारे में-
user: हाँ कर दीजिए।
assistant: अब confirm- आर्य जी!
user: Reschedule कर दीजिए।
user: ये AI की call में बार-बार वही repeat ही किया जा रहा है।
assistant: आर्य जी! आपकी delivery पिछले दो सितंबर को delivery partner के द्वारा delivery attempt की गई थी, लेकिन आप उपलब्ध नहीं थे।
assistant: मुझे खेद है
user: कल कर दीजिए ना schedule कल की।
assistant: ठीक है। आर्य जी!
assistant: आर्य जी! मैं-""",
    },
]


@pytest.mark.parametrize("case", NEW_FALSE_POSITIVE_CASES, ids=lambda c: c["id"])
def test_new_false_positive_calls_are_false(case):
    result = evaluate_delivery_scheduled_today_past(
        text_transcript_to_turns(case["transcript"]),
        logs=LOGS_SEP_2,
    )
    assert result["value"] == "false", result
    assert result["effective_new_schedule_date"] is None, result


# Load and preserve the 18 older problematic regression cases from the metric folder.
PROBLEMATIC_FILE = ROOT / "problematic_calls.json"
with PROBLEMATIC_FILE.open("r", encoding="utf-8") as f:
    PROBLEMATIC_CASES = json.load(f)


@pytest.mark.parametrize(
    "case",
    PROBLEMATIC_CASES,
    ids=[c["case_id"] for c in PROBLEMATIC_CASES],
)
def test_older_problematic_regressions(case):
    result = evaluate_delivery_scheduled_today_past(case["transcript"])
    assert result["value"] == case["expected_output"], (
        f'{case["case_id"]} ({case["name"]}): '
        f'expected={case["expected_output"]}, actual={result["value"]}, '
        f'reason={result["reason"]}, effective={result["effective_new_schedule_date"]}'
    )


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
