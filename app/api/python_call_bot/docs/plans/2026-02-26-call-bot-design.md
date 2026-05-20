# Call Bot Design - Automated Job Offer Calls

## Overview

Бот за автоматизирани обаждания чрез уеб-базирана телефонна централа (uhub.callflowlab.com). Ботът набира кандидати, представя обява за работа, слуша отговора и генерира JSON резюме.

## Technical Stack

- **Language:** Python 3.11+
- **Browser Automation:** Playwright
- **TTS:** Google Cloud Text-to-Speech (Bulgarian, bg-BG)
- **STT:** Google Cloud Speech-to-Text (Bulgarian, bg-BG)
- **Audio Bridge:** JavaScript injected into browser page

## Architecture

```
main.py (Orchestrator)
├── config.yaml              # Credentials, phone numbers, message templates
├── browser_automation.py    # Playwright - login, dial, call management
├── audio_bridge.js          # JS injected into browser for WebRTC audio manipulation
├── speech_services.py       # Google Cloud TTS + STT wrapper
├── conversation_engine.py   # State machine for conversation flow
├── call_summary.py          # JSON output generation
└── requirements.txt
```

## Approach: Playwright + JS Audio Injection

1. Playwright launches Chromium, navigates to uhub.callflowlab.com
2. Logs in with provided credentials (username, password, secret code)
3. Enters phone number and initiates call
4. JavaScript intercepts `getUserMedia` to replace mic stream with TTS-generated audio
5. JavaScript captures remote audio stream for STT processing
6. Python orchestrates conversation via state machine

## Conversation Flow (State Machine)

States:
- **DIALING** → call initiated, waiting for answer
- **GREETING** → TTS plays greeting message
- **WAITING_RESPONSE** → STT listening for user response
- **POSITIVE** → user interested → TTS plays confirmation
- **NEGATIVE** → user not interested → TTS plays thank you
- **UNCLEAR** → response not recognized → repeat question (max 1 retry)
- **CALL_ENDED** → generate JSON summary

### Response Recognition

Keyword matching on STT transcript:
- Positive: "да", "искам", "интересувам се", "разбира се", "съгласен"
- Negative: "не", "нямам", "не ме интересува", "не искам"
- Unclear: anything else → retry once, then end call

## Configuration (config.yaml)

```yaml
pbx:
  url: "https://uhub.callflowlab.com/"
  username: "103"
  password: "wB66PwAA4g"
  secret_code: "7619"

google_cloud:
  credentials_path: "./gcloud-credentials.json"
  tts_voice: "bg-BG-Standard-A"
  stt_language: "bg-BG"

call:
  phone_number: "+359895629012"
  job_posting:
    position: "Продавач-консултант"
    company: "Пепко България ЕООД"
    platform: "Джобии БГ"

messages:
  greeting: >
    Здравейте, обаждаме се от {platform} - платформа за търсене и предлагане
    на работа. Проявили сте интерес за обява {position} в {company}.
    Имате ли интерес към тази обява?
  positive_response: >
    Добре, ще предадем контактите ви на работодателя и той ще се свърже с вас.
  negative_response: >
    Добре, благодарим.
  unclear_retry: >
    Извинете, не разбрах отговора ви. Имате ли интерес към обявата за
    {position} в {company}?
```

## JSON Output Format

```json
{
  "call_id": "uuid-v4",
  "timestamp": "ISO-8601",
  "phone_number": "+359895629012",
  "job_posting": {
    "position": "Продавач-консултант",
    "company": "Пепко България ЕООД"
  },
  "duration_seconds": 45,
  "transcript": [
    {"speaker": "bot", "text": "...", "timestamp": "ISO-8601"},
    {"speaker": "user", "text": "...", "timestamp": "ISO-8601"}
  ],
  "outcome": "positive|negative|unclear|no_answer",
  "summary": "Кратко описание на резултата"
}
```

## Audio Bridge (JS Injection)

The audio bridge works by:
1. Overriding `navigator.mediaDevices.getUserMedia` before the page loads
2. Creating an `AudioContext` with a `MediaStreamDestination` as the fake mic
3. When TTS audio needs to be played, it's decoded and fed into the AudioContext
4. Remote audio is captured by intercepting `RTCPeerConnection.ontrack`
5. Remote audio is recorded via `MediaRecorder` and sent to Python for STT

## Key Risks & Mitigations

1. **WebRTC interception may break**: The web app may use non-standard WebRTC APIs
   - Mitigation: Test thoroughly, have fallback to virtual audio device approach
2. **Bulgarian STT accuracy**: Google Cloud STT may not perfectly recognize Bulgarian
   - Mitigation: Use keyword matching (not full NLU), keep expected responses simple
3. **Timing**: Need to detect when user finishes speaking
   - Mitigation: Use silence detection (VAD) from Google STT streaming API
