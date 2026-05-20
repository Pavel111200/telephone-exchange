import re
from enum import Enum
from ai_conversation import AIConversation


class State(Enum):
    DIALING = "dialing"
    GREETING = "greeting"
    WAITING_RESPONSE = "waiting_response"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CONVERSATION = "conversation"
    CALL_ENDED = "call_ended"


POSITIVE_KEYWORDS = ["да", "искам", "интересувам", "разбира се", "съгласен", "съгласна", "добре"]
NEGATIVE_KEYWORDS = ["не", "нямам", "не искам", "не ме интересува"]
QUESTION_WORDS = ["какво", "каква", "какви", "колко", "защо", "къде", "кога", "кой", "коя", "кое", "дали"]


class ConversationEngine:
    def __init__(self, messages: dict, job_posting: dict | None = None, job_description: str = ""):
        self.messages = messages
        self.state = State.DIALING
        self.exchange_count = 0
        self.max_exchanges = 6
        greeting_text = messages.get("greeting", "")
        self.ai = AIConversation(job_posting, greeting_text=greeting_text, job_description=job_description) if job_posting else None

    def call_answered(self) -> str:
        self.state = State.GREETING
        return self.messages["greeting"]

    def greeting_done(self):
        self.state = State.WAITING_RESPONSE

    def process_response(self, transcript: str) -> str | None:
        text = transcript.lower().strip()

        if not text:
            self.exchange_count += 1
            if self.exchange_count >= self.max_exchanges:
                self.state = State.CALL_ENDED
                return None
            return self.messages.get("unclear_retry", "Извинете, не ви чух. Имате ли интерес?")

        # Only use keywords for very short, unambiguous answers (not questions)
        has_positive = self._is_positive(text)
        has_negative = self._is_negative(text)
        is_question = any(qw in text for qw in QUESTION_WORDS)

        # Short, clear, not a question → keywords
        if len(text.split()) <= 3 and not (has_positive and has_negative) and not is_question:
            if has_negative:
                self.state = State.NEGATIVE
                return self.messages["negative_response"]
            if has_positive:
                self.state = State.POSITIVE
                return self.messages["positive_response"]

        # Anything else (longer response, mixed signals, questions) → AI conversation
        self.exchange_count += 1
        if self.exchange_count >= self.max_exchanges:
            self.state = State.CALL_ENDED
            return "Благодарим за отделеното време. Приятен ден!"

        if self.ai:
            ai_text, intent = self.ai.get_response(transcript)
            if intent == "positive":
                self.state = State.POSITIVE
            elif intent == "negative":
                self.state = State.NEGATIVE
            else:
                self.state = State.CONVERSATION
            return ai_text

        # Fallback without AI
        self.state = State.CONVERSATION
        return self.messages.get("unclear_retry", "Извинете, не разбрах. Имате ли интерес?")

    def process_audio(self, audio_data: bytes) -> tuple[str, str | None]:
        """Process audio directly via Gemini (merged STT+AI). Returns (transcript, bot_response)."""
        if not audio_data:
            self.exchange_count += 1
            if self.exchange_count >= self.max_exchanges:
                self.state = State.CALL_ENDED
                return "", None
            return "", self.messages.get("unclear_retry", "Извинете, не ви чух. Имате ли интерес?")

        self.exchange_count += 1
        if self.exchange_count >= self.max_exchanges:
            self.state = State.CALL_ENDED
            return "", "Благодарим за отделеното време. Приятен ден!"

        if self.ai:
            transcript, response_text, intent = self.ai.get_response_from_audio(audio_data)
            if intent == "positive":
                self.state = State.POSITIVE
            elif intent == "negative":
                self.state = State.NEGATIVE
            else:
                self.state = State.CONVERSATION
            return transcript, response_text

        return "", None

    def get_outcome(self) -> str:
        state_to_outcome = {
            State.POSITIVE: "positive",
            State.NEGATIVE: "negative",
            State.CONVERSATION: "unclear",
            State.CALL_ENDED: "unclear",
            State.DIALING: "no_answer",
        }
        return state_to_outcome.get(self.state, "unclear")

    def is_call_over(self) -> bool:
        return self.state in (State.POSITIVE, State.NEGATIVE, State.CALL_ENDED)

    def _is_positive(self, text: str) -> bool:
        return any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in POSITIVE_KEYWORDS)

    def _is_negative(self, text: str) -> bool:
        return any(re.search(r'\b' + re.escape(kw) + r'\b', text) for kw in NEGATIVE_KEYWORDS)
