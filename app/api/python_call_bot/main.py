# main.py
import asyncio
import argparse
import logging
import os
import json
import sys

from config_loader import load_config, format_message, fetch_job_description
from browser_automation import PBXAutomation
from speech_services import create_tts_service, STTService
from conversation_engine import ConversationEngine
from call_summary import CallSummary

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("call_bot")


async def wait_for_speech(pbx, timeout=10):
    """Wait until user starts speaking (or timeout). Returns True if speech detected."""
    for _ in range(int(timeout * 20)):
        state = await pbx.get_speech_state()
        if state in ("speaking", "ended"):
            return True
        await asyncio.sleep(0.05)
    return False


async def wait_for_silence(pbx, timeout=8):
    """Wait until user stops speaking (silence detected after speech)."""
    for _ in range(int(timeout * 20)):
        state = await pbx.get_speech_state()
        if state == "ended":
            return
        await asyncio.sleep(0.05)


async def record_audio(pbx, max_duration=8):
    """Record remote audio with silence detection. Returns audio bytes or None."""
    await pbx.start_recording()
    speech_detected = await wait_for_speech(pbx, timeout=max_duration)
    if speech_detected:
        await wait_for_silence(pbx, timeout=max_duration)
    return await pbx.stop_recording()


async def listen_and_transcribe(pbx, stt, max_duration=8):
    """Record remote audio and transcribe with STT."""
    audio_data = await record_audio(pbx, max_duration)
    if not audio_data:
        return ""
    return stt.transcribe(audio_data)


async def play_and_get_audio(pbx, audio_bytes, max_duration=8):
    """Play TTS with barge-in detection. Returns audio bytes if interrupted, None otherwise."""
    await pbx.start_recording()
    result = await pbx.play_tts_audio_with_barge_in(audio_bytes)

    if result.get("interrupted"):
        log.info("Barge-in detected — candidate interrupted, listening...")
        await wait_for_silence(pbx, timeout=max_duration)
        return await pbx.stop_recording()
    else:
        await pbx.stop_recording()
        return None


async def run_call(config: dict):
    job = config["call"]["job_posting"]
    phone = config["call"]["phone_number"]

    # Format messages with job posting data
    messages = {}
    for key, template in config["messages"].items():
        messages[key] = format_message(template, job)

    # If questions exist, swap positive_response with transition message
    questions = config.get("questions", [])
    positive_closing = messages["positive_response"]
    if questions:
        messages["positive_response"] = messages.get(
            "positive_with_questions",
            "Чудесно! Имам няколко кратки въпроса."
        )

    # Fetch job description from URL if configured
    job_description = ""
    job_url = job.get("url", "")
    if job_url:
        log.info(f"Fetching job description from {job_url}...")
        job_description = fetch_job_description(job_url)

    # Initialize components
    engine = ConversationEngine(messages, job_posting=job, job_description=job_description)
    summary = CallSummary(phone_number=phone, job_posting=job)
    pbx = PBXAutomation(config)

    # Set up Google Cloud credentials
    if "google_cloud" in config:
        gc = config["google_cloud"]
        if "credentials_path" in gc:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gc["credentials_path"]

    # Set up Text to Speach and Speach to Text services
    tts = create_tts_service(config)
    gc_config = config.get("google_cloud", {})
    stt = STTService(language_code=gc_config.get("stt_language", "bg-BG"))

    # Pre-synthesize all known messages (saves 1-2 sec per response during call)
    log.info("Pre-synthesizing TTS audio...")
    tts_cache = {}
    for key, text in messages.items():
        tts_cache[key] = tts.synthesize(text)
    if positive_closing != messages.get("positive_response"):
        tts_cache["positive_closing"] = tts.synthesize(positive_closing)
    for i, q in enumerate(questions):
        tts_cache[f"q_{i}"] = tts.synthesize(q)
    log.info(f"Pre-synthesized {len(tts_cache)} audio clips")

    try:
        # 1. Start browser and login
        log.info("Starting browser...")
        await pbx.start()

        log.info("Logging into PBX...")
        await pbx.login()
        await asyncio.sleep(2)

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

        # 4. Wait for connection noise to settle, then wait for user to speak
        await asyncio.sleep(1.0)
        log.info("Waiting for user to speak...")

        user_hello = ""
        for _ in range(3):  # retry if STT returns empty (noise false trigger)
            await pbx.start_recording()
            spoke = await wait_for_speech(pbx, timeout=8)
            if spoke:
                await wait_for_silence(pbx, timeout=5)
            audio_data = await pbx.stop_recording()
            if audio_data:
                user_hello = stt.transcribe(audio_data)
            if user_hello:
                log.info(f"User: {user_hello}")
                summary.add_entry("user", user_hello)
                break
            if not spoke:
                # No speech detected at all — timeout, move on
                break
            log.info("Detected noise but no speech, retrying...")

        # 5. Play greeting (small delay so beginning isn't clipped)
        await asyncio.sleep(0.3)
        greeting_text = engine.call_answered()
        log.info(f"Bot: {greeting_text}")
        summary.add_entry("bot", greeting_text)

        barge_audio = await play_and_get_audio(pbx, tts_cache["greeting"])
        engine.greeting_done()

        # Helper: transcribe + process + play response with barge-in
        async def respond_to_audio(audio_data):
            """STT → engine → TTS → play. Returns next barge-in audio or None."""
            user_text = stt.transcribe(audio_data) if audio_data else ""
            log.info(f"User: {user_text}")
            summary.add_entry("user", user_text)
            bot_reply = engine.process_response(user_text)
            if not bot_reply:
                return None
            log.info(f"Bot: {bot_reply}")
            summary.add_entry("bot", bot_reply)
            cached_key = None
            for key, text in messages.items():
                if bot_reply == text:
                    cached_key = key
                    break
            reply_audio = tts_cache[cached_key] if cached_key else tts.synthesize(bot_reply)
            if engine.is_call_over():
                # Terminal response (positive/negative farewell) — play without barge-in
                await pbx.play_tts_audio(reply_audio)
                return None
            return await play_and_get_audio(pbx, reply_audio)

        # If candidate interrupted the greeting, process
        while barge_audio and not engine.is_call_over():
            barge_audio = await respond_to_audio(barge_audio)

        # 6. Conversation loop
        while not engine.is_call_over():
            log.info("Listening for response...")
            audio_data = await record_audio(pbx)
            barge_audio = await respond_to_audio(audio_data)
            while barge_audio and not engine.is_call_over():
                barge_audio = await respond_to_audio(barge_audio)
            if engine.is_call_over():
                break

        # 7. If positive and questions configured, ask them
        if engine.get_outcome() == "positive" and questions:
            log.info("Asking candidate questions...")
            for i, q in enumerate(questions):
                log.info(f"Bot (Q): {q}")
                summary.add_entry("bot", q)
                barge_audio = await play_and_get_audio(pbx, tts_cache[f"q_{i}"])
                if barge_audio:
                    answer = stt.transcribe(barge_audio)
                else:
                    answer = await listen_and_transcribe(pbx, stt)
                log.info(f"User (A): {answer}")
                summary.add_entry("user", answer)

                # If answer looks like a counter-question, answer it via AI then re-ask
                if answer and engine.ai and any(qw in answer.lower() for qw in ["какв", "колко", "защо", "къде", "кога", "кой", "дали", "?"]):
                    ai_reply, _ = engine.ai.get_response(answer)
                    log.info(f"Bot: {ai_reply}")
                    summary.add_entry("bot", ai_reply)
                    reply_audio = tts.synthesize(ai_reply)
                    await play_and_get_audio(pbx, reply_audio)
                    # Re-ask question
                    log.info(f"Bot (Q): {q}")
                    summary.add_entry("bot", q)
                    barge_audio = await play_and_get_audio(pbx, tts_cache[f"q_{i}"])
                    if barge_audio:
                        answer = stt.transcribe(barge_audio)
                    else:
                        answer = await listen_and_transcribe(pbx, stt)
                    log.info(f"User (A): {answer}")
                    summary.add_entry("user", answer)

                summary.add_qa(q, answer)

            # Play closing message after questions
            log.info(f"Bot: {positive_closing}")
            summary.add_entry("bot", positive_closing)
            await pbx.play_tts_audio(tts_cache.get("positive_closing") or tts_cache["positive_response"])

        # 8. Set outcome and hang up
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

    # Nice summary output
    outcome_labels = {
        "positive": "ИНТЕРЕСУВА СЕ",
        "negative": "ОТКАЗВА",
        "unclear": "НЕЯСЕН ОТГОВОР",
        "no_answer": "НЕ ВДИГА",
        "error": "ГРЕШКА",
    }
    data = summary.to_dict()
    print(json.dumps(data, ensure_ascii=False), flush=True)
    
    """ print("\n" + "=" * 60)
    print(f"  РЕЗУЛТАТ ОТ ОБАЖДАНЕ")
    print("=" * 60)
    print(f"  Телефон:  {data['phone_number']}")
    print(f"  Позиция:  {data['job_posting']['position']}")
    print(f"  Компания: {data['job_posting']['company']}")
    print(f"  Времетр.: {data['duration_seconds']} сек.")
    print(f"  Статус:   {outcome_labels.get(data['outcome'], data['outcome'])}")
    if data.get("candidate_answers"):
        print("-" * 60)
        print("  ОТГОВОРИ НА КАНДИДАТА:")
        for qa in data["candidate_answers"]:
            print(f"    В: {qa['question']}")
            print(f"    О: {qa['answer'] or '(няма отговор)'}")
            print()
    print("-" * 60)
    print(f"  JSON: {filepath}")
    print("=" * 60) """


if __name__ == "__main__":
    asyncio.run(main())
