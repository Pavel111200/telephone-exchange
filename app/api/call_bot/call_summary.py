import json
import uuid
import os
from datetime import datetime, timezone

class CallSummary:
    def __init__(self, phone_number: str, job_posting: dict):
        self.call_id = str(uuid.uuid4())
        self.start_time = datetime.now(timezone.utc)
        self.phone_number = phone_number
        self.job_posting = job_posting
        self.transcript: list[dict] = []
        self.outcome: str | None = None
        self.qa_pairs: list[dict] = []

    def add_entry(self, speaker: str, text: str):
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def add_qa(self, question: str, answer: str):
        self.qa_pairs.append({"question": question, "answer": answer})

    def set_outcome(self, outcome: str):
        self.outcome = outcome

    def to_dict(self) -> dict:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()
        data = {
            "call_id": self.call_id,
            "timestamp": self.start_time.isoformat(),
            "phone_number": self.phone_number,
            "job_posting": self.job_posting,
            "duration_seconds": round(duration),
            "transcript": self.transcript,
            "outcome": self.outcome,
            "summary": self._generate_summary(),
        }
        if self.qa_pairs:
            data["candidate_answers"] = self.qa_pairs
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def save(self, output_dir: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        filename = f"call_{self.call_id}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        return filepath

    def _generate_summary(self) -> str:
        summaries = {
            "positive": "Кандидатът прояви интерес към позицията",
            "negative": "Кандидатът отказа предложението",
            "unclear": "Кандидатът не даде ясен отговор",
            "no_answer": "Кандидатът не отговори на обаждането"
        }
        return summaries.get(self.outcome, "Неизвестен резултат")
