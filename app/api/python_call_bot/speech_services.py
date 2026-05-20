import os
from google.cloud import texttospeech
from google.cloud import speech
from elevenlabs.client import ElevenLabs

class TTSService:
    def __init__(self, voice_name: str = "bg-BG-Standard-A", speaking_rate: float = 0.85):
        self.client = texttospeech.TextToSpeechClient()
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="bg-BG",
            name=voice_name
        )
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=speaking_rate
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

class STTService:
    def __init__(self, language_code: str = "bg-BG"):
        self.client = speech.SpeechClient()
        # Boost common job-call phrases for better recognition
        speech_context = speech.SpeechContext(
            phrases=[
                "заплата", "заплащане", "заплатата", "колко е заплатата",
                "каква е заплатата", "какво е заплащането",
                "позиция", "позицията", "работа", "работата",
                "график", "графикът", "работно време",
                "условия", "условията", "изисквания",
                "да", "не", "интересувам", "интересувам се",
                "откъде", "откъде се обаждате",
                "съгласен", "съгласна", "искам", "не искам",
                "кога", "къде", "как", "каква", "какво",
                "опит", "предишен опит",
                "продавач", "консултант", "управител", "магазин",
            ],
            boost=15.0
        )
        self.config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language_code,
            speech_contexts=[speech_context],
        )

    def transcribe(self, audio_data: bytes) -> str:
        audio = speech.RecognitionAudio(content=audio_data)
        response = self.client.recognize(config=self.config, audio=audio)
        if not response.results:
            return ""
        return response.results[0].alternatives[0].transcript

def create_tts_service(config: dict):
    provider = config.get("tts", {}).get("provider", "google")

    if provider == "elevenlabs":
        el_config = config.get("elevenlabs", {})
        api_key = el_config.get("api_key") or os.environ.get("ELEVENLABS_API_KEY")
        voice_id = el_config["voice_id"]
        model_id = el_config.get("model_id", "eleven_multilingual_v2")
        return ElevenLabsTTSService(api_key=api_key, voice_id=voice_id, model_id=model_id)

    if provider != "google":
        raise ValueError(f"Unknown TTS provider: '{provider}'. Supported: 'google', 'elevenlabs'")

    gc_config = config.get("google_cloud", {})
    return TTSService(
        voice_name=gc_config.get("tts_voice", "bg-BG-Standard-A"),
        speaking_rate=gc_config.get("speaking_rate", 1.0),
    )
