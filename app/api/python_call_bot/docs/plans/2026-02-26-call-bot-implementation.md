# Call Bot Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated call bot that dials candidates via a web-based PBX (uhub.callflowlab.com), delivers a job offer message via TTS, listens for the response via STT, and generates a JSON summary.

**Architecture:** Playwright automates a Chromium browser to log in and dial. JavaScript injected into the page intercepts WebRTC streams — replacing the mic with TTS audio and capturing remote audio for STT. A Python state machine orchestrates the conversation flow.

**Tech Stack:** Python 3.13, Playwright, Google Cloud TTS/STT (bg-BG), PyYAML, asyncio

---

### Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `config.yaml`
- Create: `.gitignore`

**Step 1: Initialize git repo**

```bash
cd /Users/marioivanov/Downloads/call_bot
git init
```

**Step 2: Create `.gitignore`**

```
__pycache__/
*.pyc
.venv/
gcloud-credentials.json
output/
*.wav
.DS_Store
```

**Step 3: Create `requirements.txt`**

```
playwright==1.49.1
google-cloud-texttospeech==2.21.1
google-cloud-speech==2.28.0
pyyaml==6.0.2
```

**Step 4: Create `config.yaml`**

See design doc for full config. Contains PBX credentials, Google Cloud settings, phone number, job posting details, and message templates with `{platform}`, `{position}`, `{company}` placeholders.

**Step 5: Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

**Step 6: Commit**

```bash
git add .gitignore requirements.txt config.yaml
git commit -m "chore: project setup with dependencies and config"
```

---

### Task 2: Configuration Loader

**Files:**
- Create: `config_loader.py`
- Create: `tests/test_config_loader.py`

**Step 1: Write the failing test**

```python
# tests/test_config_loader.py
import pytest
import tempfile
import os
from config_loader import load_config, format_message


def test_load_config_returns_dict():
    config = load_config("config.yaml")
    assert isinstance(config, dict)
    assert "pbx" in config
    assert "call" in config
    assert "messages" in config


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent.yaml")


def test_format_message_substitutes_placeholders():
    template = "Обява за {position} в {company} от {platform}"
    job = {"position": "Продавач", "company": "Пепко", "platform": "Джобии"}
    result = format_message(template, job)
    assert result == "Обява за Продавач в Пепко от Джобии"
```

**Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate
python -m pytest tests/test_config_loader.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'config_loader'`

**Step 3: Write minimal implementation**

```python
# config_loader.py
import yaml


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_message(template: str, job_posting: dict) -> str:
    return template.format(**job_posting)
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_config_loader.py -v
```

Expected: 3 passed

**Step 5: Commit**

```bash
git add config_loader.py tests/test_config_loader.py
git commit -m "feat: add config loader with YAML parsing and message formatting"
```

---

### Task 3: Call Summary Module

**Files:**
- Create: `call_summary.py`
- Create: `tests/test_call_summary.py`

**Step 1: Write the failing test**

```python
# tests/test_call_summary.py
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
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_call_summary.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# call_summary.py
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

    def add_entry(self, speaker: str, text: str):
        self.transcript.append({
            "speaker": speaker,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    def set_outcome(self, outcome: str):
        self.outcome = outcome

    def to_dict(self) -> dict:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - self.start_time).total_seconds()
        return {
            "call_id": self.call_id,
            "timestamp": self.start_time.isoformat(),
            "phone_number": self.phone_number,
            "job_posting": self.job_posting,
            "duration_seconds": round(duration),
            "transcript": self.transcript,
            "outcome": self.outcome,
            "summary": self._generate_summary()
        }

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
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_call_summary.py -v
```

Expected: 4 passed

**Step 5: Commit**

```bash
git add call_summary.py tests/test_call_summary.py
git commit -m "feat: add call summary module with JSON export"
```

---

### Task 4: Conversation Engine (State Machine)

**Files:**
- Create: `conversation_engine.py`
- Create: `tests/test_conversation_engine.py`

**Step 1: Write the failing test**

```python
# tests/test_conversation_engine.py
from conversation_engine import ConversationEngine, State


def make_engine():
    messages = {
        "greeting": "Здравейте, имате ли интерес?",
        "positive_response": "Ще предадем контактите ви.",
        "negative_response": "Благодарим.",
        "unclear_retry": "Не разбрах, имате ли интерес?"
    }
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


def test_unclear_response_retries_once():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    result = engine.process_response("какво?")
    assert engine.state == State.UNCLEAR
    assert result == "Не разбрах, имате ли интерес?"


def test_unclear_twice_ends_call():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    engine.process_response("какво?")
    engine.greeting_done()  # retry greeting done
    result = engine.process_response("хмм")
    assert engine.state == State.CALL_ENDED
    assert result is None


def test_get_outcome():
    engine = make_engine()
    engine.call_answered()
    engine.greeting_done()
    engine.process_response("да")
    assert engine.get_outcome() == "positive"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_conversation_engine.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# conversation_engine.py
from enum import Enum


class State(Enum):
    DIALING = "dialing"
    GREETING = "greeting"
    WAITING_RESPONSE = "waiting_response"
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNCLEAR = "unclear"
    CALL_ENDED = "call_ended"


POSITIVE_KEYWORDS = ["да", "искам", "интересувам", "разбира се", "съгласен", "съгласна", "добре"]
NEGATIVE_KEYWORDS = ["не", "нямам", "не искам", "не ме интересува"]


class ConversationEngine:
    def __init__(self, messages: dict):
        self.messages = messages
        self.state = State.DIALING
        self.retry_count = 0

    def call_answered(self) -> str:
        self.state = State.GREETING
        return self.messages["greeting"]

    def greeting_done(self):
        self.state = State.WAITING_RESPONSE

    def process_response(self, transcript: str) -> str | None:
        text = transcript.lower().strip()

        if self._is_negative(text):
            self.state = State.NEGATIVE
            return self.messages["negative_response"]

        if self._is_positive(text):
            self.state = State.POSITIVE
            return self.messages["positive_response"]

        # Unclear
        self.retry_count += 1
        if self.retry_count >= 2:
            self.state = State.CALL_ENDED
            return None

        self.state = State.UNCLEAR
        return self.messages["unclear_retry"]

    def get_outcome(self) -> str:
        state_to_outcome = {
            State.POSITIVE: "positive",
            State.NEGATIVE: "negative",
            State.UNCLEAR: "unclear",
            State.CALL_ENDED: "unclear",
            State.DIALING: "no_answer",
        }
        return state_to_outcome.get(self.state, "unclear")

    def _is_positive(self, text: str) -> bool:
        return any(kw in text for kw in POSITIVE_KEYWORDS)

    def _is_negative(self, text: str) -> bool:
        # Check for negative first — "не" at start or as standalone word
        for kw in NEGATIVE_KEYWORDS:
            if kw in text:
                return True
        return False
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_conversation_engine.py -v
```

Expected: All passed

**Step 5: Commit**

```bash
git add conversation_engine.py tests/test_conversation_engine.py
git commit -m "feat: add conversation engine state machine with keyword matching"
```

---

### Task 5: Google Cloud Speech Services

**Files:**
- Create: `speech_services.py`
- Create: `tests/test_speech_services.py`

**Prerequisites:** User must have a Google Cloud project with Speech-to-Text and Text-to-Speech APIs enabled, and a service account key saved as `gcloud-credentials.json`.

**Step 1: Write the failing test**

```python
# tests/test_speech_services.py
import pytest
from unittest.mock import patch, MagicMock
from speech_services import TTSService, STTService


class TestTTSService:
    @patch("speech_services.texttospeech.TextToSpeechClient")
    def test_synthesize_returns_audio_bytes(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.synthesize_speech.return_value.audio_content = b"fake_audio"
        mock_client_class.return_value = mock_client

        tts = TTSService(voice_name="bg-BG-Standard-A")
        audio = tts.synthesize("Здравейте")
        assert audio == b"fake_audio"
        mock_client.synthesize_speech.assert_called_once()

    @patch("speech_services.texttospeech.TextToSpeechClient")
    def test_synthesize_to_file_creates_wav(self, mock_client_class, tmp_path):
        mock_client = MagicMock()
        mock_client.synthesize_speech.return_value.audio_content = b"fake_audio"
        mock_client_class.return_value = mock_client

        tts = TTSService(voice_name="bg-BG-Standard-A")
        filepath = tts.synthesize_to_file("Здравейте", str(tmp_path / "test.wav"))
        assert filepath.endswith(".wav")


class TestSTTService:
    @patch("speech_services.speech.SpeechClient")
    def test_transcribe_returns_text(self, mock_client_class):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_alternative = MagicMock()
        mock_alternative.transcript = "да, интересувам се"
        mock_alternative.confidence = 0.95
        mock_result.alternatives = [mock_alternative]
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.recognize.return_value = mock_response
        mock_client_class.return_value = mock_client

        stt = STTService(language_code="bg-BG")
        text = stt.transcribe(b"fake_audio_data")
        assert text == "да, интересувам се"
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_speech_services.py -v
```

Expected: FAIL

**Step 3: Write minimal implementation**

```python
# speech_services.py
import os
from google.cloud import texttospeech
from google.cloud import speech


class TTSService:
    def __init__(self, voice_name: str = "bg-BG-Standard-A"):
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="bg-BG",
            name=voice_name
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000
        )

    def synthesize(self, text: str) -> bytes:
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=self.voice,
            audio_config=self.audio_config
        )
        return response.audio_content

    def synthesize_to_file(self, text: str, filepath: str) -> str:
        audio_content = self.synthesize(text)
        with open(filepath, "wb") as f:
            f.write(audio_content)
        return filepath


class STTService:
    def __init__(self, language_code: str = "bg-BG"):
        self.client = speech.SpeechClient()
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code
        )

    def transcribe(self, audio_data: bytes) -> str:
        audio = speech.RecognitionAudio(content=audio_data)
        response = self.client.recognize(config=self.config, audio=audio)
        if not response.results:
            return ""
        return response.results[0].alternatives[0].transcript
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_speech_services.py -v
```

Expected: All passed

**Step 5: Commit**

```bash
git add speech_services.py tests/test_speech_services.py
git commit -m "feat: add Google Cloud TTS and STT service wrappers"
```

---

### Task 6: Audio Bridge JavaScript

**Files:**
- Create: `audio_bridge.js`

This is the JavaScript code injected into the browser page to intercept WebRTC audio streams. It cannot be unit-tested in Python — it will be integration-tested in Task 8.

**Step 1: Create `audio_bridge.js`**

```javascript
// audio_bridge.js
// Injected into the browser page BEFORE the PBX app loads.
// Intercepts getUserMedia to replace mic with TTS audio.
// Captures remote audio from RTCPeerConnection for STT.

(function() {
    'use strict';

    // --- State ---
    let audioContext = null;
    let fakeStreamDest = null;   // MediaStreamAudioDestinationNode (fake mic)
    let remoteRecorder = null;
    let remoteChunks = [];
    let isRecording = false;

    // --- Initialize audio context and fake mic stream ---
    function initAudioContext() {
        if (audioContext) return;
        audioContext = new AudioContext({ sampleRate: 16000 });
        fakeStreamDest = audioContext.createMediaStreamDestination();
        // Add a silent oscillator so the stream is "active"
        const silence = audioContext.createOscillator();
        const gain = audioContext.createGain();
        gain.gain.value = 0;
        silence.connect(gain);
        gain.connect(fakeStreamDest);
        silence.start();
    }

    // --- Override getUserMedia to return fake mic ---
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(
        navigator.mediaDevices
    );

    navigator.mediaDevices.getUserMedia = async function(constraints) {
        if (constraints && constraints.audio) {
            initAudioContext();
            // If video is also requested, get real video but fake audio
            if (constraints.video) {
                const realStream = await originalGetUserMedia({ video: constraints.video });
                const combined = new MediaStream();
                realStream.getVideoTracks().forEach(t => combined.addTrack(t));
                fakeStreamDest.stream.getAudioTracks().forEach(t => combined.addTrack(t));
                return combined;
            }
            return fakeStreamDest.stream;
        }
        return originalGetUserMedia(constraints);
    };

    // --- Intercept RTCPeerConnection to capture remote audio ---
    const OriginalRTCPeerConnection = window.RTCPeerConnection;

    window.RTCPeerConnection = function(...args) {
        const pc = new OriginalRTCPeerConnection(...args);

        pc.addEventListener('track', (event) => {
            if (event.track.kind === 'audio') {
                window.__callbot_remoteStream = event.streams[0];
                window.dispatchEvent(
                    new CustomEvent('callbot:remoteAudio', { detail: event.streams[0] })
                );
            }
        });

        return pc;
    };
    window.RTCPeerConnection.prototype = OriginalRTCPeerConnection.prototype;

    // --- API exposed to Playwright (via window object) ---

    // Play TTS audio (base64-encoded WAV) through fake mic
    window.__callbot_playAudio = async function(base64Audio) {
        initAudioContext();
        const binaryStr = atob(base64Audio);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }
        const audioBuffer = await audioContext.decodeAudioData(bytes.buffer);
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(fakeStreamDest);
        return new Promise(resolve => {
            source.onended = () => resolve(true);
            source.start();
        });
    };

    // Start recording remote audio
    window.__callbot_startRecording = function() {
        const stream = window.__callbot_remoteStream;
        if (!stream) return false;
        remoteChunks = [];
        remoteRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        remoteRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) remoteChunks.push(e.data);
        };
        remoteRecorder.start(100); // collect every 100ms
        isRecording = true;
        return true;
    };

    // Stop recording and return base64 audio
    window.__callbot_stopRecording = function() {
        return new Promise(resolve => {
            if (!remoteRecorder || !isRecording) {
                resolve(null);
                return;
            }
            remoteRecorder.onstop = async () => {
                const blob = new Blob(remoteChunks, { type: 'audio/webm' });
                const arrayBuffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(arrayBuffer);
                let binary = '';
                for (let i = 0; i < bytes.length; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                resolve(btoa(binary));
                isRecording = false;
            };
            remoteRecorder.stop();
        });
    };

    // Check if remote stream is available
    window.__callbot_hasRemoteAudio = function() {
        return !!window.__callbot_remoteStream;
    };

    console.log('[CallBot] Audio bridge initialized');
})();
```

**Step 2: Commit**

```bash
git add audio_bridge.js
git commit -m "feat: add audio bridge JS for WebRTC interception"
```

---

### Task 7: Browser Automation (Playwright)

**Files:**
- Create: `browser_automation.py`

This module handles login, dialing, and audio bridge injection. Cannot be fully unit-tested as it depends on the live PBX web interface. Will be tested via manual integration in Task 8.

**Step 1: Create `browser_automation.py`**

```python
# browser_automation.py
import asyncio
import base64
import os
from playwright.async_api import async_playwright, Page, Browser


class PBXAutomation:
    def __init__(self, config: dict):
        self.config = config
        self.browser: Browser | None = None
        self.page: Page | None = None
        self._playwright = None

    async def start(self):
        """Launch browser and inject audio bridge."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=False,  # Need headed for WebRTC
            args=[
                "--use-fake-ui-for-media-stream",   # auto-allow mic/camera
                "--autoplay-policy=no-user-gesture-required"
            ]
        )
        context = await self.browser.new_context(
            permissions=["microphone", "camera"]
        )
        self.page = await context.new_page()

        # Inject audio bridge before page loads
        js_path = os.path.join(os.path.dirname(__file__), "audio_bridge.js")
        with open(js_path, "r") as f:
            bridge_js = f.read()
        await self.page.add_init_script(bridge_js)

    async def login(self):
        """Log into the PBX web interface."""
        pbx = self.config["pbx"]
        await self.page.goto(pbx["url"])
        await self.page.wait_for_load_state("networkidle")

        # Fill login form — selectors may need adjustment after inspecting the page
        await self.page.fill('input[name="username"], input[type="text"]', pbx["username"])
        await self.page.fill('input[name="password"], input[type="password"]', pbx["password"])

        # If there's a secret code field
        secret_input = self.page.locator('input[name="secret"], input[name="code"]')
        if await secret_input.count() > 0:
            await secret_input.fill(pbx["secret_code"])

        await self.page.click('button[type="submit"], input[type="submit"]')
        await self.page.wait_for_load_state("networkidle")

    async def dial(self, phone_number: str):
        """Enter phone number and initiate call."""
        # Find the dial input and enter number — selectors may need adjustment
        dial_input = self.page.locator(
            'input[type="tel"], input[name="number"], input[placeholder*="номер"], '
            'input[placeholder*="number"], input.dial-input'
        )
        await dial_input.fill(phone_number)

        # Click call/dial button
        call_button = self.page.locator(
            'button.call-btn, button.dial-btn, button[title*="Call"], '
            'button[title*="обаж"], a.call-button'
        )
        await call_button.click()

    async def wait_for_call_connected(self, timeout: int = 30000):
        """Wait until the remote party answers (remote audio stream appears)."""
        for _ in range(timeout // 500):
            has_audio = await self.page.evaluate("window.__callbot_hasRemoteAudio()")
            if has_audio:
                return True
            await asyncio.sleep(0.5)
        return False

    async def play_tts_audio(self, audio_bytes: bytes):
        """Play TTS audio through the fake mic (into the WebRTC call)."""
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        await self.page.evaluate(f"window.__callbot_playAudio('{b64}')")

    async def start_recording(self):
        """Start recording remote audio."""
        await self.page.evaluate("window.__callbot_startRecording()")

    async def stop_recording(self) -> bytes | None:
        """Stop recording and return audio bytes."""
        b64 = await self.page.evaluate("window.__callbot_stopRecording()")
        if not b64:
            return None
        return base64.b64decode(b64)

    async def hangup(self):
        """Click hangup button."""
        hangup_btn = self.page.locator(
            'button.hangup-btn, button.end-call, button[title*="Hangup"], '
            'button[title*="затвор"], button.btn-danger'
        )
        if await hangup_btn.count() > 0:
            await hangup_btn.click()

    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
```

**Step 2: Commit**

```bash
git add browser_automation.py
git commit -m "feat: add Playwright browser automation for PBX login and dial"
```

---

### Task 8: Main Orchestrator

**Files:**
- Create: `main.py`
- Create: `tests/__init__.py`

**Step 1: Create `tests/__init__.py`**

Empty file.

**Step 2: Create `main.py`**

```python
# main.py
import asyncio
import argparse
import logging
import os

from config_loader import load_config, format_message
from browser_automation import PBXAutomation
from speech_services import TTSService, STTService
from conversation_engine import ConversationEngine
from call_summary import CallSummary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("call_bot")


async def run_call(config: dict):
    job = config["call"]["job_posting"]
    phone = config["call"]["phone_number"]

    # Format messages with job posting data
    messages = {}
    for key, template in config["messages"].items():
        messages[key] = format_message(template, job)

    # Initialize components
    engine = ConversationEngine(messages)
    summary = CallSummary(phone_number=phone, job_posting=job)
    pbx = PBXAutomation(config)

    # Set up Google Cloud credentials
    if "google_cloud" in config:
        gc = config["google_cloud"]
        if "credentials_path" in gc:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gc["credentials_path"]

    tts = TTSService(voice_name=config.get("google_cloud", {}).get("tts_voice", "bg-BG-Standard-A"))
    stt = STTService(language_code=config.get("google_cloud", {}).get("stt_language", "bg-BG"))

    try:
        # 1. Start browser and login
        log.info("Starting browser...")
        await pbx.start()

        log.info("Logging into PBX...")
        await pbx.login()
        await asyncio.sleep(2)  # Wait for PBX to fully load

        # 2. Dial
        log.info(f"Dialing {phone}...")
        await pbx.dial(phone)

        # 3. Wait for answer
        log.info("Waiting for call to connect...")
        connected = await pbx.wait_for_call_connected(timeout=30000)
        if not connected:
            log.warning("Call not answered within timeout")
            summary.set_outcome("no_answer")
            return summary

        log.info("Call connected!")

        # 4. Play greeting
        greeting_text = engine.call_answered()
        log.info(f"Bot: {greeting_text}")
        summary.add_entry("bot", greeting_text)

        greeting_audio = tts.synthesize(greeting_text)
        await pbx.play_tts_audio(greeting_audio)
        engine.greeting_done()

        # 5. Listen for response
        log.info("Listening for response...")
        await pbx.start_recording()
        await asyncio.sleep(5)  # Record for 5 seconds
        audio_data = await pbx.stop_recording()

        if audio_data:
            user_text = stt.transcribe(audio_data)
            log.info(f"User: {user_text}")
            summary.add_entry("user", user_text)

            # 6. Process response
            bot_reply = engine.process_response(user_text)

            if bot_reply:
                log.info(f"Bot: {bot_reply}")
                summary.add_entry("bot", bot_reply)
                reply_audio = tts.synthesize(bot_reply)
                await pbx.play_tts_audio(reply_audio)

                # If unclear, listen again
                if engine.state.value == "unclear":
                    engine.greeting_done()
                    await pbx.start_recording()
                    await asyncio.sleep(5)
                    audio_data2 = await pbx.stop_recording()

                    if audio_data2:
                        user_text2 = stt.transcribe(audio_data2)
                        log.info(f"User: {user_text2}")
                        summary.add_entry("user", user_text2)

                        bot_reply2 = engine.process_response(user_text2)
                        if bot_reply2:
                            log.info(f"Bot: {bot_reply2}")
                            summary.add_entry("bot", bot_reply2)
                            reply_audio2 = tts.synthesize(bot_reply2)
                            await pbx.play_tts_audio(reply_audio2)
        else:
            log.warning("No audio captured from user")

        # 7. Set outcome and hang up
        summary.set_outcome(engine.get_outcome())
        await asyncio.sleep(1)
        await pbx.hangup()

    except Exception as e:
        log.error(f"Error during call: {e}")
        summary.set_outcome("error")
        raise
    finally:
        await pbx.close()

    return summary


async def main():
    parser = argparse.ArgumentParser(description="Call Bot - Automated Job Offer Calls")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--output", default="output", help="Output directory for call summaries")
    parser.add_argument("--phone", help="Override phone number from config")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.phone:
        config["call"]["phone_number"] = args.phone

    summary = await run_call(config)
    filepath = summary.save(args.output)

    log.info(f"Call completed. Outcome: {summary.outcome}")
    log.info(f"Summary saved to: {filepath}")
    print("\n--- Call Summary ---")
    print(summary.to_json())


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 3: Commit**

```bash
git add main.py tests/__init__.py
git commit -m "feat: add main orchestrator tying all components together"
```

---

### Task 9: Manual Integration Testing & Selector Tuning

**Files:**
- Modify: `browser_automation.py` (selectors will likely need adjustment)

This task CANNOT be automated. It requires:

**Step 1: Inspect the PBX web interface**

```bash
source .venv/bin/activate
python -c "
import asyncio
from playwright.async_api import async_playwright

async def inspect():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=False)
    page = await browser.new_page()
    await page.goto('https://uhub.callflowlab.com/')
    await page.wait_for_load_state('networkidle')
    # Pause here to inspect the page manually
    await page.pause()
    await browser.close()
    await pw.stop()

asyncio.run(inspect())
"
```

**Step 2: Note the exact CSS selectors for:**
- Username input
- Password input
- Secret code input
- Login/submit button
- Phone number input field
- Call/dial button
- Hangup button

**Step 3: Update selectors in `browser_automation.py`**

Replace the generic selectors with the exact ones found in Step 2.

**Step 4: Run a test call**

```bash
source .venv/bin/activate
python main.py --phone "+359895629012"
```

**Step 5: Commit selector fixes**

```bash
git add browser_automation.py
git commit -m "fix: update PBX selectors after manual inspection"
```

---

### Task 10: Final Verification

**Step 1: Run all unit tests**

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: All tests pass.

**Step 2: Run full integration test with real call**

```bash
python main.py --config config.yaml
```

Verify:
- Browser opens and logs in
- Number is dialed
- Greeting is spoken
- User response is captured and transcribed
- Appropriate reply is given
- JSON summary is saved to `output/` directory

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: final verification complete"
```
