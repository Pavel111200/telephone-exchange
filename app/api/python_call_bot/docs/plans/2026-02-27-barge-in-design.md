# Barge-in: Stop playback when candidate speaks

## Goal

Allow the bot to detect when a candidate speaks during TTS playback, stop the audio immediately, listen to what they say, and respond naturally.

## Problem

Currently `playAudio()` blocks until the TTS clip finishes. Recording only starts after playback ends. If a candidate speaks during playback, the bot is "deaf" — it misses the speech entirely, making the conversation feel artificial.

## Architecture

Monitor remote audio stream in parallel with TTS playback. If candidate speech is detected (RMS > threshold for 200ms), stop playback immediately and capture what was said.

## Changes

### audio_bridge.js

- Add `__callbot_playAudioWithBargeIn()` function:
  - Starts monitoring remote stream RMS levels while playing TTS audio
  - If remote speech detected (RMS > SPEECH_THRESHOLD for 200ms) → stops playback (`source.stop()`), resolves with `{interrupted: true}`
  - If playback finishes normally → resolves with `{interrupted: false}`
  - Recording should be started BEFORE playback so it captures the candidate's speech from the start

### browser_automation.py

- Add `play_tts_audio_with_barge_in()` method that calls the new JS function and returns `{interrupted: bool}`

### main.py

- New `play_and_listen()` async function:
  - Starts recording, then plays audio with barge-in detection
  - If interrupted: waits for candidate to finish speaking (silence detection), stops recording, transcribes, processes response
  - If not interrupted: stops recording (discard noise), continues normal flow
- Replace `play_tts_audio()` calls in the conversation loop with `play_and_listen()`

## Unchanged

- `speech_services.py` — no change
- `conversation_engine.py` — no change
- `config.yaml` — barge-in threshold is a constant in audio_bridge.js (200ms)
