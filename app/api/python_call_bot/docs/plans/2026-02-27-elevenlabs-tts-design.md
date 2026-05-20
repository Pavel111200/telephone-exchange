# ElevenLabs TTS Integration Design

## Goal

Add ElevenLabs as a TTS provider alongside Google Cloud TTS, selectable via config. ElevenLabs produces more natural-sounding speech for Bulgarian.

## Architecture

Both TTS providers share the same interface: `synthesize(text: str) -> bytes` returning WAV 24kHz. A factory function `create_tts_service(config)` returns the correct provider based on `tts.provider` in config.yaml.

## Changes

### config.yaml

New top-level `tts` section with `provider` field. New `elevenlabs` section with `api_key`, `voice_id`, `model_id`.

```yaml
tts:
  provider: "elevenlabs"  # or "google"

elevenlabs:
  api_key: "sk-..."  # or env var ELEVENLABS_API_KEY
  voice_id: "21m00Tcm4TlvDq8ikWAM"  # Rachel (female)
  model_id: "eleven_multilingual_v2"
```

### speech_services.py

- Add `ElevenLabsTTSService` class with `synthesize(text) -> bytes`
  - Uses `elevenlabs` Python SDK with `output_format="wav_24000"` (direct WAV, no conversion needed)
- Add `create_tts_service(config)` factory function

### main.py

- Replace direct `TTSService(...)` instantiation with `create_tts_service(config)`

### requirements.txt

- Add `elevenlabs`

## Unchanged

- `audio_bridge.js` — receives WAV bytes, no change needed
- `conversation_engine.py` — unaware of TTS
- `browser_automation.py` — `play_tts_audio(bytes)` is provider-agnostic
