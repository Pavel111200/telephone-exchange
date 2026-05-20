import pytest
from unittest.mock import patch, MagicMock
from speech_services import TTSService, STTService, ElevenLabsTTSService, create_tts_service

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

    def test_unknown_provider_raises_error(self):
        config = {"tts": {"provider": "azure"}}
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            create_tts_service(config)
