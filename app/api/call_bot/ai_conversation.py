# ai_conversation.py
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types


class AIConversation:
    def __init__(self, job_posting: dict, greeting_text: str = "", job_description: str = ""):
        
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY in .env")
        
        self.client = genai.Client(api_key=api_key)
        self.job = job_posting

        # Build job info block from description if available
        if job_description:
            job_info_block = f"""
Информация от обявата:
---
{job_description}
---
"""
            answer_rule = """- Ако кандидатът пита за детайли (заплата, график, изисквания и т.н.) и информацията е в обявата по-горе, отговори кратко с данните от обявата
- Ако информацията НЕ е в обявата, кажи че работодателят ще даде повече информация при контакт"""
        else:
            job_info_block = ""
            answer_rule = "- НЕ измисляй детайли за заплата или условия - кажи че работодателят ще даде повече информация"

        self.system_prompt = f"""Ти си учтив телефонен асистент на платформата "{job_posting['platform']}" - платформа за търсене и предлагане на работа.
Обаждаш се на кандидат, който е проявил интерес към обява за позиция "{job_posting['position']}" в "{job_posting['company']}".
{job_info_block}
Правила:
- Говори САМО на български език
- Бъди кратък - максимум 2 изречения на отговор
- Целта ти е да разбереш дали кандидатът все още се интересува от тази позиция
- НЕ повтаряй представянето - то вече е направено в началото на разговора
- Ако кандидатът е съгласен, кажи че ще предадеш контактите му на работодателя
- Ако кандидатът откаже, благодари учтиво
{answer_rule}
- Отговорът ти ТРЯБВА да започва с един от тези тагове:
  [POSITIVE] - ако кандидатът е съгласен/заинтересован
  [NEGATIVE] - ако кандидатът отказва
  [CONTINUE] - ако разговорът продължава (въпрос, неясен отговор, и т.н.)

Пример:
Потребител: "А каква е заплатата?"
Ти: "[CONTINUE] Според обявата заплатата е от 1200 до 1500 лв. Имате ли интерес да предадем контактите ви?"
"""
        self.history: list[types.Content] = []
        # Add greeting as context so AI knows what was already said
        if greeting_text:
            self.history.append(types.Content(
                role="model", parts=[types.Part(text=greeting_text.strip())]
            ))

    def _parse_intent(self, text: str) -> tuple[str, str]:
        """Extract intent tag from response text. Returns (clean_text, intent)."""
        for tag, tag_intent in [("[POSITIVE]", "positive"), ("[NEGATIVE]", "negative"), ("[CONTINUE]", "continue")]:
            if text.startswith(tag):
                return text[len(tag):].strip(), tag_intent
        return text, "continue"

    def get_response(self, user_text: str) -> tuple[str, str]:
        """Returns (response_text, intent) where intent is 'positive', 'negative', or 'continue'."""
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=self.history,
            config=types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                max_output_tokens=200,
                temperature=0.3
            )
        )

        text = response.text.strip()
        self.history.append(types.Content(role="model", parts=[types.Part(text=text)]))
        return self._parse_intent(text)

    def get_response_from_audio(self, audio_data: bytes) -> tuple[str, str, str]:
        """Process audio directly — transcribe + respond in one Gemini call.
        Returns (transcript, response_text, intent)."""
        audio_part = types.Part.from_bytes(data=audio_data, mime_type="audio/webm")

        audio_instruction = self.system_prompt + """
ДОПЪЛНИТЕЛНО: Получаваш аудио запис на потребителя. Първо го транскрибирай, после отговори.
Форматът ТРЯБВА да бъде точно:
TRANSCRIPT: <точна транскрипция на казаното>
[POSITIVE/NEGATIVE/CONTINUE] <твоят отговор>
"""

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=self.history + [types.Content(role="user", parts=[audio_part])],
            config=types.GenerateContentConfig(
                system_instruction=audio_instruction,
                max_output_tokens=300,
                temperature=0.3
            )
        )

        text = response.text.strip()

        # Parse TRANSCRIPT: line and response
        transcript = ""
        response_text = text
        lines = text.split("\n", 1)
        if lines[0].upper().startswith("TRANSCRIPT:"):
            transcript = lines[0].split(":", 1)[1].strip()
            response_text = lines[1].strip() if len(lines) > 1 else ""

        response_text, intent = self._parse_intent(response_text)

        # Store as text in history (not audio, to avoid re-sending large data)
        if transcript:
            self.history.append(types.Content(role="user", parts=[types.Part(text=transcript)]))
        self.history.append(types.Content(role="model", parts=[types.Part(text=response_text)]))

        return transcript, response_text, intent
