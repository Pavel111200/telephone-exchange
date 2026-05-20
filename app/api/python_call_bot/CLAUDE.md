# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated recruitment call bot that logs into a web-based PBX (uhub.callflowlab.com) via Playwright, dials candidates, plays a TTS greeting in Bulgarian, conducts AI-powered conversations via STT + Gemini, and generates JSON call summaries.

## Commands

```bash
# Setup (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Google Cloud auth
gcloud auth application-default login
gcloud auth application-default set-quota-project YOUR_PROJECT_ID

# Run
python main.py
python main.py --phone "+359888123456"
python main.py --config production.yaml --output logs
LOGLEVEL=DEBUG python main.py

# Test
python -m pytest tests/ -v
python -m pytest tests/test_conversation_engine.py -v                              # single module
python -m pytest tests/test_conversation_engine.py::test_positive_response -v      # single test
```

## Architecture

```
main.py (async orchestrator)
├── config_loader.py         # YAML config + {position}/{company}/{platform} template formatting + job URL scraping
├── browser_automation.py    # Playwright: PBX login (with optional 2FA), dial, hangup
│   └── audio_bridge.js      # Injected via add_init_script() before page load
├── speech_services.py       # TTS (Google Cloud or ElevenLabs) + Google Cloud STT
│   └── create_tts_service() # Factory: returns TTSService or ElevenLabsTTSService based on config
├── conversation_engine.py   # State machine: DIALING→GREETING→WAITING_RESPONSE→[POSITIVE|NEGATIVE|CONVERSATION]→CALL_ENDED
│   └── ai_conversation.py   # Gemini 2.0 Flash via Vertex AI (europe-west1) for complex/ambiguous responses
└── call_summary.py          # JSON report: transcript, outcome, Q&A pairs → output/call_{uuid}.json
```

### Key Design Decisions

- **Two-tier response processing**: Short unambiguous responses (≤3 words) use regex keyword matching on Bulgarian positive/negative words. Longer or ambiguous responses go through Gemini AI. This reduces API costs and latency.
- **Audio format asymmetry**: TTS outputs LINEAR16 WAV at 24kHz (for WebRTC playback); STT consumes WEBM OPUS at 48kHz (from browser MediaRecorder). Different sample rates are intentional.
- **TTS provider selection**: `config.yaml` `tts.provider` chooses between `"google"` and `"elevenlabs"`. Both output WAV 24kHz. ElevenLabs API key can be set via config or `ELEVENLABS_API_KEY` env var.
- **TTS pre-synthesis**: Known messages (greeting, closings, questions) are synthesized once during setup and cached in `tts_cache`. Only AI-generated responses need live TTS.
- **Barge-in detection**: `play_tts_audio_with_barge_in()` stops playback if the candidate speaks during TTS. The interrupted audio is captured and processed as the candidate's response, avoiding a separate listen step.
- **audio_bridge.js** overrides `getUserMedia()` for a fake mic and intercepts `RTCPeerConnection.ontrack` for remote audio capture. Exposes window APIs: `__callbot_playAudio`, `__callbot_playAudioWithBargeIn`, `__callbot_startRecording`, `__callbot_stopRecording`, `__callbot_getSpeechState`, `__callbot_hasRemoteAudio`.
- **Silence detection (VAD)**: RMS amplitude monitoring in audio_bridge.js with SPEECH_THRESHOLD=8 and SILENCE_DURATION=150ms.
- **Conversation limits**: Engine ends call after max 6 exchanges. Follow-up questions are asked after positive intent is confirmed, before hangup. During questions, counter-questions from the candidate are answered via AI then the question is re-asked.
- **AI intent tags**: Gemini responses must start with `[POSITIVE]`, `[NEGATIVE]`, or `[CONTINUE]` to drive state transitions. Parsed by `AIConversation._parse_intent()`.
- **Merged STT+AI path**: `process_audio()` / `get_response_from_audio()` sends raw audio to Gemini for combined transcription and response in a single API call (returns `TRANSCRIPT:` line + tagged response).
- **Job description context**: If `call.job_posting.url` is set, `config_loader.fetch_job_description()` scrapes the page (max 3000 chars) and injects it into the Gemini system prompt so the bot can answer candidate questions about salary, schedule, etc.

### Call Flow

1. Load config → fetch job description URL → pre-synthesize TTS → launch browser → inject audio_bridge.js
2. Login to PBX (handles 2FA if configured) → dial candidate
3. Wait for remote audio (`hasRemoteAudio()`) → wait for user hello → play greeting with barge-in detection
4. Loop: record audio with VAD → transcribe via STT → process response → synthesize + play reply (with barge-in)
5. On terminal state → ask follow-up questions if positive → play closing → hangup → save JSON summary

## Configuration

`config.yaml` holds PBX credentials, TTS provider settings, Google Cloud settings, ElevenLabs settings, phone number, job posting data (including URL for scraping), message templates, and optional follow-up questions. Message templates support `{position}`, `{company}`, `{platform}` placeholders.

## Important Notes

- All I/O is async (`asyncio`). Use `asyncio.sleep()`, not `time.sleep()`.
- PBX selectors in `browser_automation.py` are specific to uhub.callflowlab.com and may need updating if UI changes.
- Language is Bulgarian (bg-BG) throughout: TTS voice, STT config, keyword lists, AI system prompt.
- Call outcomes: `positive`, `negative`, `unclear`, `no_answer`, `error`.
- Browser runs in headed mode (`headless=False`) — required for WebRTC audio to work.
- Gemini AI is accessed via Vertex AI (`google-genai` client with `vertexai=True`), not the consumer API. Project is hardcoded as `jobee-development` in `ai_conversation.py`.
- Tests in `tests/` only cover `ConversationEngine` without AI (no `job_posting` passed). They test the keyword-matching path and state transitions.
