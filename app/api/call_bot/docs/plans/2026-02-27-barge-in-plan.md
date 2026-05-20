# Barge-in Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Detect when the candidate speaks during TTS playback, stop audio immediately, and process what they said.

**Architecture:** Add `__callbot_playAudioWithBargeIn()` in audio_bridge.js that plays TTS while monitoring remote stream RMS. If speech detected for 200ms, stop playback and resolve with `{interrupted: true}`. In main.py, start recording before playback so the candidate's speech is captured from the start. Then transcribe and process normally.

**Tech Stack:** JavaScript (Web Audio API), Python (asyncio), Playwright

---

### Task 1: Add `__callbot_playAudioWithBargeIn` to audio_bridge.js

**Files:**
- Modify: `audio_bridge.js:78-96`

**Step 1: Add the new function after `__callbot_playAudio`**

Add this code after the existing `__callbot_playAudio` function (after line 96), before `__callbot_startRecording`:

```javascript
// Play TTS audio with barge-in detection — stops if candidate speaks
window.__callbot_playAudioWithBargeIn = async function(base64Audio) {
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

    // Set up barge-in detection on remote stream
    const remoteStream = window.__callbot_remoteStream;
    if (!remoteStream) {
        // No remote stream — fall back to normal playback
        return new Promise(resolve => {
            source.onended = () => resolve({ interrupted: false });
            source.start();
        });
    }

    const bargeCtx = new AudioContext();
    const analyser = bargeCtx.createAnalyser();
    analyser.fftSize = 256;
    const remoteSource = bargeCtx.createMediaStreamSource(remoteStream);
    remoteSource.connect(analyser);
    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    const BARGE_IN_THRESHOLD = 8;    // Same as SPEECH_THRESHOLD
    const BARGE_IN_DURATION = 200;   // ms of continuous speech to trigger barge-in

    let speechStart = null;

    return new Promise(resolve => {
        const bargeInterval = setInterval(() => {
            analyser.getByteTimeDomainData(dataArray);
            let sum = 0;
            for (let i = 0; i < dataArray.length; i++) {
                const val = (dataArray[i] - 128) / 128;
                sum += val * val;
            }
            const rms = Math.sqrt(sum / dataArray.length) * 100;

            if (rms > BARGE_IN_THRESHOLD) {
                if (!speechStart) speechStart = Date.now();
                if (Date.now() - speechStart >= BARGE_IN_DURATION) {
                    // Barge-in detected — stop playback
                    clearInterval(bargeInterval);
                    bargeCtx.close().catch(() => {});
                    try { source.stop(); } catch(e) {}
                    resolve({ interrupted: true });
                }
            } else {
                speechStart = null;
            }
        }, 30);

        source.onended = () => {
            clearInterval(bargeInterval);
            bargeCtx.close().catch(() => {});
            resolve({ interrupted: false });
        };

        source.start();
    });
};
```

**Step 2: Test manually in browser console (not automated)**

This is a JS function injected into a browser — no unit test framework. Manual verification during integration test.

**Step 3: Commit**

```bash
git add audio_bridge.js
git commit -m "feat: add playAudioWithBargeIn for barge-in detection"
```

---

### Task 2: Add `play_tts_audio_with_barge_in` to browser_automation.py

**Files:**
- Modify: `browser_automation.py:88-91`

**Step 1: Add the new method after `play_tts_audio`**

Add after line 91 (after the existing `play_tts_audio` method):

```python
async def play_tts_audio_with_barge_in(self, audio_bytes: bytes) -> dict:
    """Play TTS audio with barge-in detection. Returns {'interrupted': bool}."""
    b64 = base64.b64encode(audio_bytes).decode("ascii")
    result = await self.page.evaluate(f"window.__callbot_playAudioWithBargeIn('{b64}')")
    return result
```

**Step 2: Commit**

```bash
git add browser_automation.py
git commit -m "feat: add play_tts_audio_with_barge_in method"
```

---

### Task 3: Add `play_and_listen` function to main.py

**Files:**
- Modify: `main.py`

**Step 1: Add `play_and_listen` function after `listen_and_transcribe` (after line 48)**

```python
async def play_and_listen(pbx, stt, audio_bytes, max_duration=8):
    """Play TTS audio while listening for barge-in. Returns transcribed text or empty string."""
    await pbx.start_recording()
    result = await pbx.play_tts_audio_with_barge_in(audio_bytes)

    if result.get("interrupted"):
        log.info("Barge-in detected — candidate interrupted, listening...")
        # Candidate already started speaking; wait for them to finish
        await wait_for_silence(pbx, timeout=max_duration)
        audio_data = await pbx.stop_recording()
        if not audio_data:
            return ""
        return stt.transcribe(audio_data)
    else:
        # No interruption — stop recording, discard any noise
        await pbx.stop_recording()
        return ""
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add play_and_listen function for barge-in support"
```

---

### Task 4: Wire barge-in into the greeting playback

**Files:**
- Modify: `main.py:140-147`

**Step 1: Replace the greeting playback block**

Replace lines 140-147:

```python
        # 5. Play greeting (small delay so beginning isn't clipped)
        await asyncio.sleep(0.3)
        greeting_text = engine.call_answered()
        log.info(f"Bot: {greeting_text}")
        summary.add_entry("bot", greeting_text)

        await pbx.play_tts_audio(tts_cache["greeting"])
        engine.greeting_done()
```

With:

```python
        # 5. Play greeting with barge-in detection
        await asyncio.sleep(0.3)
        greeting_text = engine.call_answered()
        log.info(f"Bot: {greeting_text}")
        summary.add_entry("bot", greeting_text)

        barge_in_text = await play_and_listen(pbx, stt, tts_cache["greeting"])
        engine.greeting_done()

        # If candidate interrupted the greeting, process their response immediately
        if barge_in_text:
            log.info(f"User (barge-in): {barge_in_text}")
            summary.add_entry("user", barge_in_text)
            bot_reply = engine.process_response(barge_in_text)
            if bot_reply:
                log.info(f"Bot: {bot_reply}")
                summary.add_entry("bot", bot_reply)
                cached_key = None
                for key, text in messages.items():
                    if bot_reply == text:
                        cached_key = key
                        break
                reply_audio = tts_cache[cached_key] if cached_key else tts.synthesize(bot_reply)
                await pbx.play_tts_audio(reply_audio)
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add barge-in detection to greeting playback"
```

---

### Task 5: Wire barge-in into the conversation loop

**Files:**
- Modify: `main.py:149-171`

**Step 1: Replace the bot reply playback in the conversation loop**

In the conversation loop (around lines 158-168), replace:

```python
                await pbx.play_tts_audio(reply_audio)
```

With:

```python
                barge_text = await play_and_listen(pbx, stt, reply_audio)
                if barge_text:
                    log.info(f"User (barge-in): {barge_text}")
                    summary.add_entry("user", barge_text)
                    bot_reply = engine.process_response(barge_text)
                    if bot_reply:
                        log.info(f"Bot: {bot_reply}")
                        summary.add_entry("bot", bot_reply)
                        cached_key = None
                        for key, text in messages.items():
                            if bot_reply == text:
                                cached_key = key
                                break
                        reply_audio = tts_cache[cached_key] if cached_key else tts.synthesize(bot_reply)
                        await pbx.play_tts_audio(reply_audio)
```

**Step 2: Wire barge-in into question playback (lines 176-184)**

Replace:

```python
                await pbx.play_tts_audio(tts_cache[f"q_{i}"])

                answer = await listen_and_transcribe(pbx, stt)
```

With:

```python
                barge_text = await play_and_listen(pbx, stt, tts_cache[f"q_{i}"])
                if barge_text:
                    answer = barge_text
                else:
                    answer = await listen_and_transcribe(pbx, stt)
```

**Step 3: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (no tests touch barge-in directly — it's integration-level)

**Step 4: Commit**

```bash
git add main.py
git commit -m "feat: add barge-in to conversation loop and questions"
```

---

### Task 6: Integration test — run a real call

**Step 1: Run a test call**

```bash
source .venv/bin/activate
python main.py
```

**Step 2: Verify barge-in behavior**

- During the greeting, try speaking — the bot should stop and listen
- Verify logs show "Barge-in detected" and "User (barge-in):" entries
- Verify the conversation continues naturally after barge-in

**Step 3: If barge-in triggers too easily on noise**

Increase `BARGE_IN_DURATION` in `audio_bridge.js` from 200 to 300 or 400.

**Step 4: If barge-in doesn't trigger**

Decrease `BARGE_IN_THRESHOLD` in `audio_bridge.js` from 8 to 5 or 6.
