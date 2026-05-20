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

    // --- Silence detection state ---
    let speechState = 'waiting';  // 'waiting' | 'speaking' | 'ended'
    let silenceTimer = null;
    let monitorInterval = null;
    let monitorCtx = null;
    const SPEECH_THRESHOLD = 8;    // RMS level to consider as speech (filters connection noise)
    const SILENCE_DURATION = 150;  // ms of silence after speech to mark "ended"

    // --- Initialize audio context and fake mic stream ---
    function initAudioContext() {
        if (audioContext) return;
        audioContext = new AudioContext({ sampleRate: 24000 });
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

        const BARGE_IN_THRESHOLD = 1.5;   // Lower than SPEECH_THRESHOLD — remote audio is quieter during playback
        const BARGE_IN_DURATION = 200;   // ms of cumulative speech to trigger barge-in
        const GRACE_PERIOD = 150;        // ms — allow brief RMS dips without resetting (syllable gaps)

        let speechStart = null;
        let lastSpeechTime = null;
        let logCounter = 0;

        return new Promise(resolve => {
            const bargeInterval = setInterval(() => {
                analyser.getByteTimeDomainData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) {
                    const val = (dataArray[i] - 128) / 128;
                    sum += val * val;
                }
                const rms = Math.sqrt(sum / dataArray.length) * 100;

                // DEBUG: log RMS every 500ms
                if (logCounter++ % 17 === 0) {
                    console.log('[BargeIn] RMS:', rms.toFixed(2), 'threshold:', BARGE_IN_THRESHOLD, 'speechStart:', !!speechStart);
                }

                if (rms > BARGE_IN_THRESHOLD) {
                    if (!speechStart) speechStart = Date.now();
                    lastSpeechTime = Date.now();
                    if (Date.now() - speechStart >= BARGE_IN_DURATION) {
                        // Barge-in detected — stop playback
                        clearInterval(bargeInterval);
                        bargeCtx.close().catch(() => {});
                        try { source.stop(); } catch(e) {}
                        resolve({ interrupted: true });
                    }
                } else if (speechStart && (Date.now() - lastSpeechTime > GRACE_PERIOD)) {
                    // Only reset after sustained silence (grace period elapsed)
                    speechStart = null;
                    lastSpeechTime = null;
                }
                // If within grace period, keep speechStart — allows brief dips between syllables
            }, 30);

            source.onended = () => {
                clearInterval(bargeInterval);
                bargeCtx.close().catch(() => {});
                resolve({ interrupted: false });
            };

            source.start();
        });
    };

    // Start recording remote audio (with silence detection)
    window.__callbot_startRecording = function() {
        const stream = window.__callbot_remoteStream;
        if (!stream) return false;

        // Stop and discard any existing recording
        if (remoteRecorder) {
            try { remoteRecorder.stop(); } catch(e) {}
            remoteRecorder = null;
            isRecording = false;
        }

        remoteChunks = [];
        speechState = 'waiting';
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
        if (monitorInterval) { clearInterval(monitorInterval); monitorInterval = null; }
        if (monitorCtx) { monitorCtx.close().catch(() => {}); monitorCtx = null; }

        // Set up audio level monitoring for silence detection
        try {
            monitorCtx = new AudioContext();
            const analyser = monitorCtx.createAnalyser();
            analyser.fftSize = 256;
            const source = monitorCtx.createMediaStreamSource(stream);
            source.connect(analyser);
            const dataArray = new Uint8Array(analyser.frequencyBinCount);

            monitorInterval = setInterval(() => {
                if (speechState === 'ended') {
                    clearInterval(monitorInterval);
                    monitorInterval = null;
                    return;
                }
                analyser.getByteTimeDomainData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) {
                    const val = (dataArray[i] - 128) / 128;
                    sum += val * val;
                }
                const rms = Math.sqrt(sum / dataArray.length) * 100;

                if (rms > SPEECH_THRESHOLD) {
                    speechState = 'speaking';
                    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
                } else if (speechState === 'speaking' && !silenceTimer) {
                    silenceTimer = setTimeout(() => {
                        speechState = 'ended';
                    }, SILENCE_DURATION);
                }
            }, 50);
        } catch (e) {
            console.warn('[CallBot] Could not set up silence detection:', e);
        }

        // Start MediaRecorder
        try {
            remoteRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            remoteRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) remoteChunks.push(e.data);
            };
            remoteRecorder.start(100);
            isRecording = true;
            return true;
        } catch(e) {
            console.warn('[CallBot] MediaRecorder start failed:', e);
            remoteRecorder = null;
            return false;
        }
    };

    // Stop recording and return base64 audio
    window.__callbot_stopRecording = function() {
        return new Promise(resolve => {
            if (!remoteRecorder || !isRecording) {
                resolve(null);
                return;
            }
            // Clean up silence detection
            if (monitorInterval) { clearInterval(monitorInterval); monitorInterval = null; }
            if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
            if (monitorCtx) { monitorCtx.close().catch(() => {}); monitorCtx = null; }

            remoteRecorder.onstop = async () => {
                const blob = new Blob(remoteChunks, { type: 'audio/webm' });
                const arrayBuffer = await blob.arrayBuffer();
                const bytes = new Uint8Array(arrayBuffer);
                let binary = '';
                for (let i = 0; i < bytes.length; i++) {
                    binary += String.fromCharCode(bytes[i]);
                }
                isRecording = false;
                remoteRecorder = null;
                resolve(btoa(binary));
            };
            remoteRecorder.stop();
        });
    };

    // Get current speech state for silence detection
    window.__callbot_getSpeechState = function() {
        return speechState;
    };

    // Check if remote stream is available
    window.__callbot_hasRemoteAudio = function() {
        return !!window.__callbot_remoteStream;
    };

    console.log('[CallBot] Audio bridge initialized');
})();
