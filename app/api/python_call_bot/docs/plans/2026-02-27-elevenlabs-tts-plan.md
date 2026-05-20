# ElevenLabs TTS Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ElevenLabs as a configurable TTS provider alongside Google Cloud TTS.

**Architecture:** Factory pattern — `create_tts_service(config)` returns either `TTSService` (Google) or `ElevenLabsTTSService` based on `tts.provider` in config.yaml. Both classes expose `synthesize(text) -> bytes` returning WAV 24kHz. ElevenLabs SDK outputs WAV directly via `output_format="wav_24000"`, so no audio conversion is needed.

**Tech Stack:** `elevenlabs` Python SDK, existing `speech_services.py` module

---

### Task 1: Add ElevenLabsTTSService tests

**Files:**
- Modify: `tests/test_speech_services.py`

**Step 1: Write the failing tests**

Add to `tests/test_speech_services.py`:

```python
from speech_services import ElevenLabsTTSService, create_tts_service

class TestElevenLabsTTSService:
    @patch("speech_services.ElevenLabs")
    def test_synthesize_returns_audio_bytes(self, mock_elevenlabs_class):
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"fake_wav_audio"])
        mock_elevenlabs_class.return_value = mock_client

        tts = ElevenLabsTTSService(api_key="test-key", voice_id="test-voice")
        audio = tts.synthesize("Здравейте")

        assert audio == b"fake_wav_audio"
        mock_client.text_to_speech.convert.assert_called_once()
        call_kwargs = mock_client.text_to_speech.convert.call_args[1]
        assert call_kwargs["output_format"] == "wav_24000"
        assert call_kwargs["voice_id"] == "test-voice"

    @patch("speech_services.ElevenLabs")
    def test_synthesize_concatenates_chunks(self, mock_elevenlabs_class):
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"chunk1", b"chunk2"])
        mock_elevenlabs_class.return_value = mock_client

        tts = ElevenLabsTTSService(api_key="test-key", voice_id="test-voice")
        audio = tts.synthesize("Здравейте")

        assert audio == b"chunk1chunk2"

    @patch("speech_services.ElevenLabs")
    def test_uses_api_key(self, mock_elevenlabs_class):
        ElevenLabsTTSService(api_key="my-secret-key", voice_id="v1")
        mock_elevenlabs_class.assert_called_once_with(api_key="my-secret-key")

    @patch("speech_services.ElevenLabs")
    def test_uses_model_id(self, mock_elevenlabs_class):
        mock_client = MagicMock()
        mock_client.text_to_speech.convert.return_value = iter([b"audio"])
        mock_elevenlabs_class.return_value = mock_client

        tts = ElevenLabsTTSService(api_key="k", voice_id="v", model_id="eleven_v3")
        tts.synthesize("test")

        call_kwargs = mock_client.text_to_speech.convert.call_args[1]
        assert call_kwargs["model_id"] == "eleven_v3"
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_speech_services.py -v`
Expected: FAIL — `ImportError: cannot import name 'ElevenLabsTTSService'`

---

### Task 2: Implement ElevenLabsTTSService

**Files:**
- Modify: `speech_services.py`

**Step 3: Write the implementation**

Add to `speech_services.py` after the existing `TTSService` class (before `STTService`):

```python
from elevenlabs.client import ElevenLabs

class ElevenLabsTTSService:
    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_multilingual_v2"):
        self.client = ElevenLabs(api_key=api_key)
        self.voice_id = voice_id
        self.model_id = model_id

    def synthesize(self, text: str) -> bytes:
        audio_iter = self.client.text_to_speech.convert(
            text=text,
            voice_id=self.voice_id,
            model_id=self.model_id,
            output_format="wav_24000",
        )
        return b"".join(audio_iter)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_speech_services.py::TestElevenLabsTTSService -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add speech_services.py tests/test_speech_services.py
git commit -m "feat: add ElevenLabsTTSService with wav_24000 output"
```

---

### Task 3: Add create_tts_service factory tests

**Files:**
- Modify: `tests/test_speech_services.py`

**Step 6: Write the failing tests**

Add to `tests/test_speech_services.py`:

```python
class TestCreateTTSService:
    @patch("speech_services.texttospeech.TextToSpeechClient")
    def test_google_provider(self, mock_client):
        config = {
            "tts": {"provider": "google"},
            "google_cloud": {"tts_voice": "bg-BG-Chirp3-HD-Kore", "speaking_rate": 1.0},
        }
        service = create_tts_service(config)
        assert isinstance(service, TTSService)

    @patch("speech_services.ElevenLabs")
    def test_elevenlabs_provider(self, mock_client):
        config = {
            "tts": {"provider": "elevenlabs"},
            "elevenlabs": {"api_key": "sk-test", "voice_id": "v1"},
        }
        service = create_tts_service(config)
        assert isinstance(service, ElevenLabsTTSService)

    @patch("speech_services.ElevenLabs")
    def test_elevenlabs_api_key_from_env(self, mock_client, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "env-key")
        config = {
            "tts": {"provider": "elevenlabs"},
            "elevenlabs": {"voice_id": "v1"},
        }
        service = create_tts_service(config)
        assert isinstance(service, ElevenLabsTTSService)
        mock_client.assert_called_once_with(api_key="env-key")

    @patch("speech_services.texttospeech.TextToSpeechClient")
    def test_defaults_to_google(self, mock_client):
        config = {"google_cloud": {"tts_voice": "bg-BG-Standard-A"}}
        service = create_tts_service(config)
        assert isinstance(service, TTSService)
```

**Step 7: Run tests to verify they fail**

Run: `python -m pytest tests/test_speech_services.py::TestCreateTTSService -v`
Expected: FAIL — `ImportError: cannot import name 'create_tts_service'`

---

### Task 4: Implement create_tts_service factory

**Files:**
- Modify: `speech_services.py`

**Step 8: Write the implementation**

Add to the bottom of `speech_services.py` (after `STTService`):

```python
def create_tts_service(config: dict):
    provider = config.get("tts", {}).get("provider", "google")

    if provider == "elevenlabs":
        el_config = config.get("elevenlabs", {})
        api_key = el_config.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
        voice_id = el_config["voice_id"]
        model_id = el_config.get("model_id", "eleven_multilingual_v2")
        return ElevenLabsTTSService(api_key=api_key, voice_id=voice_id, model_id=model_id)

    gc_config = config.get("google_cloud", {})
    return TTSService(
        voice_name=gc_config.get("tts_voice", "bg-BG-Standard-A"),
        speaking_rate=gc_config.get("speaking_rate", 1.0),
    )
```

**Step 9: Run ALL speech service tests**

Run: `python -m pytest tests/test_speech_services.py -v`
Expected: All tests PASS (existing Google tests + new ElevenLabs + factory tests)

**Step 10: Commit**

```bash
git add speech_services.py tests/test_speech_services.py
git commit -m "feat: add create_tts_service factory for provider selection"
```

---

### Task 5: Update main.py to use factory

**Files:**
- Modify: `main.py`

**Step 11: Update the import**

Change line 9:
```python
# Before:
from speech_services import TTSService, STTService
# After:
from speech_services import create_tts_service, STTService
```

**Step 12: Replace TTSService instantiation**

Replace lines 80-84:
```python
# Before:
gc_config = config.get("google_cloud", {})
tts = TTSService(
    voice_name=gc_config.get("tts_voice", "bg-BG-Standard-A"),
    speaking_rate=gc_config.get("speaking_rate", 1.0)
)

# After:
tts = create_tts_service(config)
```

**Step 13: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 14: Commit**

```bash
git add main.py
git commit -m "refactor: use create_tts_service factory in main.py"
```

---

### Task 6: Update config.yaml and requirements.txt

**Files:**
- Modify: `config.yaml`
- Modify: `requirements.txt`

**Step 15: Add ElevenLabs config section to config.yaml**

Add after the `google_cloud` section:

```yaml
tts:
  provider: "elevenlabs"  # "elevenlabs" or "google"

elevenlabs:
  # API key (or set ELEVENLABS_API_KEY env var)
  api_key: ""
  voice_id: "21m00Tcm4TlvDq8ikWAM"  # Rachel (female)
  model_id: "eleven_multilingual_v2"
```

**Step 16: Add elevenlabs to requirements.txt**

Append: `elevenlabs>=1.0.0`

**Step 17: Install new dependency**

Run: `pip install elevenlabs>=1.0.0`

**Step 18: Run full test suite one final time**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 19: Commit**

```bash
git add config.yaml requirements.txt
git commit -m "feat: add ElevenLabs config and dependency"
```
