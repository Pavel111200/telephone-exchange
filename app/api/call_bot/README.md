# Call Bot

Automated phone call bot for job recruitment. Calls candidates via a web-based PBX, plays a TTS greeting, conducts an AI-powered conversation in Bulgarian, asks configurable follow-up questions, and generates a JSON summary.

## How It Works

1. Logs into a WebRTC-based PBX via Playwright browser automation
2. Dials the candidate's phone number
3. Waits for the candidate to answer
4. Plays a TTS greeting about the job posting (with barge-in detection — stops if candidate speaks)
5. Listens for the response — uses keyword matching for short answers, Google Gemini AI for longer/ambiguous ones
6. If the candidate asks questions (e.g. about salary), the bot answers using info from the job posting URL
7. If the candidate is interested, asks configurable follow-up questions
8. Hangs up and saves a JSON summary with transcript, outcome, and candidate answers

## Setup

### Prerequisites

- Python 3.11+
- Google Cloud account with TTS, STT, and Vertex AI APIs enabled
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- ElevenLabs account (optional, for higher quality TTS)

### Installation

```bash
cd call_bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Google Cloud Authentication

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID jobee_development
```

Required APIs (enable via `gcloud services enable`):
- `texttospeech.googleapis.com`
- `speech.googleapis.com`
- `aiplatform.googleapis.com`

## Usage

```bash
source .venv/bin/activate
python main.py
```

### Options

```
--phone "+359888123456"    Override phone number from config
--config other.yaml        Use a different config file
--output results           Change output directory (default: output/)
```

### Examples

```bash
# Use config defaults
python main.py

# Call a specific number
python main.py --phone "+359888123456"

# Different config and output dir
python main.py --config production.yaml --output logs
```

## Configuration

Edit `config.yaml`:

```yaml
pbx:
  url: "https://uhub.callflowlab.com/"
  username: "103"
  password: "your_password"
  client_id: "jobee"
  secret_code: "7619"
  secret_answer: "София"

tts:
  provider: "elevenlabs"  # "elevenlabs" or "google"

elevenlabs:
  api_key: "your_api_key"  # or set ELEVENLABS_API_KEY env var
  voice_id: "your_voice_id"
  model_id: "eleven_turbo_v2_5"  # fast, low-latency model

google_cloud:
  tts_voice: "bg-BG-Chirp3-HD-Kore"
  speaking_rate: 1.1
  stt_language: "bg-BG"

call:
  phone_number: "+359888123456"
  job_posting:
    position: "Продавач-консултант"
    company: "Пепко България"
    platform: "Джоби Бе Ге"
    url: "https://example.com/job/123"  # job posting URL — bot answers candidate questions from it

messages:
  greeting: >
    Здравейте, обаждаме се от {platform}...
  positive_response: >
    Добре, ще предадем контактите ви...
  positive_with_questions: >
    Чудесно! Имам няколко кратки въпроса...
  negative_response: >
    Добре, благодарим. Приятен ден!
  unclear_retry: >
    Извинете, не разбрах отговора ви...

questions:
  - "Кога бихте могли да започнете работа?"
  - "Имате ли предишен опит на подобна позиция?"
```

Message templates support `{position}`, `{company}`, and `{platform}` placeholders.

## Output

Each call generates a JSON file in the output directory:

```json
{
  "call_id": "uuid",
  "timestamp": "2026-03-02T14:15:08Z",
  "phone_number": "+359888123456",
  "job_posting": { "position": "...", "company": "...", "platform": "..." },
  "duration_seconds": 61,
  "transcript": [
    { "speaker": "bot", "text": "Здравейте...", "timestamp": "..." },
    { "speaker": "user", "text": "да, интересувам се", "timestamp": "..." }
  ],
  "outcome": "positive",
  "summary": "Кандидатът прояви интерес към позицията",
  "candidate_answers": [
    { "question": "Кога бихте могли да започнете работа?", "answer": "от следващата седмица" },
    { "question": "Имате ли предишен опит?", "answer": "да, 2 години" }
  ]
}
```

Possible outcomes: `positive`, `negative`, `unclear`, `no_answer`, `error`

## Project Structure

```
call_bot/
├── main.py                 # Entry point and async call orchestration
├── config.yaml             # Configuration
├── config_loader.py        # YAML config loading, message formatting, job URL fetching
├── conversation_engine.py  # State machine for call flow
├── ai_conversation.py      # Gemini 2.0 Flash AI conversation handler
├── speech_services.py      # Google Cloud TTS/STT + ElevenLabs TTS
├── browser_automation.py   # Playwright PBX automation
├── audio_bridge.js         # JS injected into browser for WebRTC audio + barge-in detection
├── call_summary.py         # JSON call report generation
├── requirements.txt        # Python dependencies
├── tests/                  # Unit tests
└── output/                 # Generated call summaries
```

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```
