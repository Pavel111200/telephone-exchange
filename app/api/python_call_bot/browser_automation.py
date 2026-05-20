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
            headless=False,
            args=[
                "--use-fake-ui-for-media-stream",
                "--autoplay-policy=no-user-gesture-required"
            ]
        )
        context = await self.browser.new_context(
            permissions=["microphone", "camera"]
        )
        self.page = await context.new_page()

        # Capture browser console for debugging
        self.page.on("console", lambda msg: print(f"[BROWSER] {msg.text}") if "BargeIn" in msg.text else None)

        # Inject audio bridge before page loads
        js_path = os.path.join(os.path.dirname(__file__), "audio_bridge.js")
        with open(js_path, "r") as f:
            bridge_js = f.read()
        await self.page.add_init_script(bridge_js)

    async def login(self):
        """Log into the PBX web interface (handles two-step auth)."""
        pbx = self.config["pbx"]
        await self.page.goto(pbx["url"])
        await self.page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Step 1: Login form
        await self.page.fill('#username', pbx["username"])
        await self.page.fill('#password', pbx["password"])
        await self.page.fill('#clientid', pbx["client_id"])

        # Security code - 4 jQuery UI select dropdowns (hidden, set via JS)
        code = pbx["secret_code"]
        await self.page.evaluate('''(code) => {
            for (let i = 0; i < 4; i++) {
                const select = document.querySelector('select[name="safe_code_' + (i+1) + '"]');
                select.value = code[i];
                if (typeof jQuery !== 'undefined') jQuery(select).selectmenu('refresh');
            }
        }''', code)

        await self.page.click('div.submit')
        await asyncio.sleep(5)

        # Step 2: Additional authentication (secret question)
        if 'additional-authentication' in self.page.url:
            await self.page.fill('#secret_answer', pbx.get("secret_answer", ""))
            remember = self.page.locator('input[name="remember_ip"]')
            if await remember.count() > 0:
                await remember.check()
            await self.page.locator('div.submit').first.click()
            await asyncio.sleep(8)

        # Wait for PBX panel to be ready
        await self.page.wait_for_selector('#phone-number', timeout=15000)

    async def dial(self, phone_number: str):
        """Enter phone number and initiate call."""
        await self.page.fill('#phone-number', phone_number)
        await asyncio.sleep(0.5)
        await self.page.click('a#dial')

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

    async def play_tts_audio_with_barge_in(self, audio_bytes: bytes) -> dict:
        """Play TTS audio with barge-in detection. Returns {'interrupted': bool}."""
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        result = await self.page.evaluate(f"window.__callbot_playAudioWithBargeIn('{b64}')")
        return result

    async def start_recording(self):
        """Start recording remote audio."""
        await self.page.evaluate("window.__callbot_startRecording()")

    async def get_speech_state(self) -> str:
        """Get speech detection state: 'waiting', 'speaking', or 'ended'."""
        return await self.page.evaluate("window.__callbot_getSpeechState()")

    async def stop_recording(self) -> bytes | None:
        """Stop recording and return audio bytes."""
        b64 = await self.page.evaluate("window.__callbot_stopRecording()")
        if not b64:
            return None
        return base64.b64decode(b64)

    async def hangup(self):
        """Click hangup button."""
        hangup_btn = self.page.locator('a#hangup')
        if await hangup_btn.count() > 0:
            await hangup_btn.click()

    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
