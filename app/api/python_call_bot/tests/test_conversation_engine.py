from conversation_engine import ConversationEngine, State


def make_engine():
    messages = {
        "greeting": "Здравейте, имате ли интерес?",
        "positive_response": "Ще предадем контактите ви.",
        "negative_response": "Благодарим.",
        "unclear_retry": "Не разбрах, имате ли интерес?"
    }
    # No job_posting = no AI, uses fallback
    return ConversationEngine(messages)


def test_initial_state():
    engine = make_engine()
    assert engine.state == State.DIALING


def test_call_answered_transitions_to_greeting():
    engine = make_engine()
    result = engine.call_answered()
    assert engine.state == State.GREETING
    assert result == "Здравейте, имате ли интерес?"


def test_greeting_done_transitions_to_waiting():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    assert engine.state == State.WAITING_RESPONSE


def test_positive_response():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    result = engine.process_response("да, искам")
    assert engine.state == State.POSITIVE
    assert result == "Ще предадем контактите ви."


def test_negative_response():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    result = engine.process_response("не, благодаря")
    assert engine.state == State.NEGATIVE
    assert result == "Благодарим."


def test_unclear_goes_to_conversation():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    result = engine.process_response("какво?")
    assert engine.state == State.CONVERSATION
    assert result is not None


def test_empty_response_retries():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    result = engine.process_response("")
    assert result == "Не разбрах, имате ли интерес?"


def test_max_exchanges_ends_call():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    engine.process_response("")  # exchange 1
    engine.process_response("")  # exchange 2
    result = engine.process_response("")  # exchange 3
    assert engine.state == State.CALL_ENDED
    assert result is None


def test_get_outcome():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    engine.process_response("да")
    assert engine.get_outcome() == "positive"


def test_is_call_over():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    assert not engine.is_call_over()
    engine.process_response("да")
    assert engine.is_call_over()
