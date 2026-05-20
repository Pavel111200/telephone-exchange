import json
from call_summary import CallSummary

def test_create_summary():
    summary = CallSummary(
        phone_number="+359895629012",
        job_posting={"position": "Продавач", "company": "Пепко"}
    )
    assert summary.phone_number == "+359895629012"
    assert summary.outcome is None

def test_add_transcript_entry():
    summary = CallSummary(
        phone_number="+359895629012",
        job_posting={"position": "Продавач", "company": "Пепко"}
    )
    summary.add_entry("bot", "Здравейте")
    summary.add_entry("user", "Да")
    assert len(summary.transcript) == 2
    assert summary.transcript[0]["speaker"] == "bot"
    assert summary.transcript[1]["text"] == "Да"

def test_to_json():
    summary = CallSummary(
        phone_number="+359895629012",
        job_posting={"position": "Продавач", "company": "Пепко"}
    )
    summary.add_entry("bot", "Здравейте")
    summary.set_outcome("positive")
    result = summary.to_json()
    data = json.loads(result)
    assert data["phone_number"] == "+359895629012"
    assert data["outcome"] == "positive"
    assert "call_id" in data
    assert "timestamp" in data
    assert "duration_seconds" in data
    assert len(data["transcript"]) == 1

def test_save_to_file(tmp_path):
    summary = CallSummary(
        phone_number="+359895629012",
        job_posting={"position": "Продавач", "company": "Пепко"}
    )
    summary.set_outcome("negative")
    filepath = summary.save(str(tmp_path))
    assert filepath.endswith(".json")
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["outcome"] == "negative"
