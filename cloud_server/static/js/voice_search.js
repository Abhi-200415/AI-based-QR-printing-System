/**
 * AI Voice Assistant - Strict Tap-To-Activate Controller
 * 
 * Hard Security & Privacy Constraints:
 * 1. Microphone is NEVER auto-started on page load.
 * 2. Microphone is activated ONLY upon explicit user tap.
 * 3. Continuous listening is strictly forbidden (continuous = false).
 * 4. Recognition stops immediately once speech is captured.
 * 5. Structured interpretation requires user confirmation before applying.
 * 6. Role-based authorization: Customers cannot trigger owner commands.
 */

(function(window) {
    'use strict';

    const WORD_TO_NUMBER = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5
    };

    /**
     * Dispatch structured voice telemetry event to cloud server for terminal logging.
     */
    function sendVoiceTelemetry(event, command = null, intent = null, detail = null) {
        try {
            fetch('/ai/voice-command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    event: event,
                    command: command ? String(command).substring(0, 100) : null,
                    intent: intent ? String(intent) : null,
                    detail: detail ? String(detail).substring(0, 150) : null
                })
            }).catch(() => {});
        } catch (e) {
            // Telemetry failure should never crash client
        }
    }

    /**
     * Text-to-speech confirmation using standard browser SpeechSynthesis.
     */
    function speakText(text) {
        if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) {
            return;
        }
        try {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.lang = 'en-US';
            window.speechSynthesis.speak(utterance);
        } catch (e) {
            console.warn("Speech synthesis error:", e);
        }
    }

    class AIVoiceAssistant {
        constructor() {
            this.recognition = null;
            this.isListening = false;
            this.state = 'READY'; // READY, LISTENING, PROCESSING, RESULT, ERROR
            this.onStateChangeCallback = null;
            this.onResultCallback = null;
            this.lastCommandText = "";
            this.lastExecutionTime = 0;
            this.initSpeechRecognition();
        }

        initSpeechRecognition() {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {
                console.warn("Web Speech API is not supported in this browser.");
                return;
            }

            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false; // STRICT REQUIREMENT: Single phrase only!
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US';

            this.recognition.onstart = () => {
                this.isListening = true;
                this.setState('LISTENING');
                sendVoiceTelemetry('MIC_ACTIVATED');
            };

            this.recognition.onresult = (event) => {
                this.setState('PROCESSING');
                this.stopListening();

                if (event.results && event.results.length > 0) {
                    const transcript = event.results[0][0].transcript.trim();
                    const confidence = event.results[0][0].confidence;
                    this.handleSpeechInput(transcript, confidence);
                } else {
                    sendVoiceTelemetry('UNCLEAR', '', 'EMPTY', 'No transcript returned');
                    this.setState('READY');
                }
            };

            this.recognition.onerror = (event) => {
                console.warn("Speech recognition error:", event.error);
                this.stopListening();
                sendVoiceTelemetry('RECOGNITION_FAILED', null, null, event.error);

                const errMsg = event.error === 'not-allowed'
                    ? "Microphone access denied. Please grant permission."
                    : event.error === 'no-speech'
                    ? "No speech detected. Please tap and speak clearly."
                    : `Voice error: ${event.error}`;

                this.setState('ERROR', errMsg);
            };

            this.recognition.onend = () => {
                this.isListening = false;
                if (this.state === 'LISTENING') {
                    this.setState('READY');
                }
            };
        }

        setState(state, detail = null) {
            this.state = state;
            if (this.onStateChangeCallback) {
                this.onStateChangeCallback(state, detail);
            }
        }

        /**
         * Explicit tap-to-activate trigger.
         */
        startListening() {
            if (!this.recognition) {
                this.setState('ERROR', "Voice recognition is not supported in this browser.");
                return;
            }
            if (this.isListening) {
                this.stopListening();
                return;
            }

            try {
                this.recognition.start();
            } catch (err) {
                console.warn("Failed to start voice recognition:", err);
                this.stopListening();
            }
        }

        stopListening() {
            this.isListening = false;
            if (this.recognition) {
                try {
                    this.recognition.stop();
                } catch (e) {
                    // Ignore already stopped
                }
            }
        }

        /**
         * Natural language voice command parser.
         * Distinguishes:
         * - Greetings: "hello", "hi", "hey"
         * - Help / Questions: "help", "what can you do"
         * - Navigation requests: "open dashboard", "show dashboard"
         * - Preview: "preview", "show my file"
         * - Summary: "checkout", "order summary", "show price"
         * - Actual application actions: copies, color mode, duplex, paper size, finishing
         * - Ambiguous: single keywords without details ("print", "document")
         */
        parseCommand(rawText) {
            const text = (rawText || "").toLowerCase().trim();
            const result = {
                raw: rawText,
                intent: 'CONFIGURE_PRINT', // GREETING, HELP, NAVIGATION, PREVIEW, SUMMARY, CONFIGURE_PRINT, AMBIGUOUS, UNKNOWN
                targetFile: null,
                copies: null,
                printType: null,
                duplex: null,
                paperSize: null,
                pageRanges: null,
                finishingService: null,
                navigationTarget: null,
                message: null
            };

            if (!text) {
                result.intent = 'UNKNOWN';
                result.message = "No speech detected. Please tap the mic and try again.";
                return result;
            }

            // 1. Greetings
            if (/^(hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)\b/i.test(text)) {
                result.intent = 'GREETING';
                result.message = "Hello! I am your AI print assistant. Tell me how you'd like your documents printed, such as copies, color mode, or paper size.";
                return result;
            }

            // 2. Help / Question queries
            if (/\b(help|what can you do|how does this work|commands|what should i say)\b/i.test(text)) {
                result.intent = 'HELP';
                result.message = "You can say: '2 copies in color', 'double sided', 'A4 size', or 'add spiral binding'.";
                return result;
            }

            // 3. Navigation / Role-gated actions
            if (text.includes("open dashboard") || text.includes("show dashboard") || text.includes("owner settings") || text.includes("admin")) {
                result.intent = 'NAVIGATION';
                result.navigationTarget = 'DASHBOARD';
                result.message = "Role Restricted: Dashboard navigation requires shop owner authentication.";
                return result;
            }

            // 4. Preview commands
            if (text.includes("preview") || text.includes("show my file") || text.includes("view document") || text.includes("show preview")) {
                result.intent = 'PREVIEW';
                result.message = "Opening document preview.";
                return result;
            }

            // 5. Order summary / Proceed to checkout
            if (text.includes("show price") || text.includes("order summary") || text.includes("checkout") || text.includes("proceed") || text.includes("calculate price") || text.includes("pay now")) {
                result.intent = 'SUMMARY';
                result.message = "Proceeding to checkout.";
                return result;
            }

            if (text.includes("show status") || text.includes("track order") || text.includes("order status")) {
                result.intent = 'STATUS';
                result.message = "Checking current order status.";
                return result;
            }

            // 6. Identify target file index
            const fileMatch = text.match(/(?:file|document|doc)\s*(\d+|one|two|three|four|five|first|second|third)/i);
            if (fileMatch) {
                const rawNum = fileMatch[1].toLowerCase();
                result.targetFile = WORD_TO_NUMBER[rawNum] || parseInt(rawNum) || 1;
            }

            // 7. Extract Copies
            const copiesMatch = text.match(/(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*cop(?:y|ies)/i);
            if (copiesMatch) {
                const cVal = copiesMatch[1].toLowerCase();
                result.copies = WORD_TO_NUMBER[cVal] || parseInt(cVal) || 1;
            } else {
                const numMatch = text.match(/\b(\d+)\s*(?:print|pages?|sets?)/i);
                if (numMatch) result.copies = parseInt(numMatch[1]);
            }

            // 8. Extract Color Mode
            if (text.includes("black and white") || text.includes("b and w") || text.includes("b&w") || text.includes("grayscale") || text.includes("monochrome") || text.includes("bw")) {
                result.printType = "BW";
            } else if (text.includes("full color") || text.includes("colour") || text.includes("color")) {
                result.printType = "COLOR";
            } else if (text.includes("mixed")) {
                result.printType = "MIXED";
            }

            // 9. Extract Duplex / Sides
            if (text.includes("double-sided") || text.includes("double sided") || text.includes("duplex") || text.includes("two-sided") || text.includes("both sides") || text.includes("2-sided") || text.includes("front and back")) {
                result.duplex = true;
            } else if (text.includes("single-sided") || text.includes("single sided") || text.includes("1-sided") || text.includes("one-sided") || text.includes("front only") || text.includes("simplex")) {
                result.duplex = false;
            }

            // 10. Extract Paper Size
            if (text.includes("a3")) {
                result.paperSize = "A3";
            } else if (text.includes("legal")) {
                result.paperSize = "LEGAL";
            } else if (text.includes("a4")) {
                result.paperSize = "A4";
            }

            // 11. Extract Finishing Services
            if (text.includes("spiral binding") || text.includes("spiral") || text.includes("binding")) {
                result.finishingService = "Spiral Binding";
            } else if (text.includes("lamination") || text.includes("laminate")) {
                result.finishingService = "Lamination";
            } else if (text.includes("glass sheet") || text.includes("transparent sheet") || text.includes("transparent")) {
                result.finishingService = "Transparent/Glass Sheet";
            } else if (text.includes("stapling") || text.includes("staple")) {
                result.finishingService = "Stapling";
            } else if (text.includes("envelope")) {
                result.finishingService = "Envelope";
            }

            // 12. Extract Page Range
            const rangeMatch = text.match(/pages?\s*(\d+\s*(?:to|-)\s*\d+|\d+)/i);
            if (rangeMatch) {
                result.pageRanges = rangeMatch[1].replace(/\s*to\s*/i, "-");
            }

            // 13. Verify if any configuration was detected
            const hasSettings = result.copies !== null || result.printType !== null || 
                                result.duplex !== null || result.paperSize !== null || 
                                result.finishingService !== null || result.pageRanges !== null;

            if (hasSettings) {
                result.intent = 'CONFIGURE_PRINT';
                return result;
            }

            // 14. Check for ambiguous single keywords
            const ambiguousWords = ["print", "document", "file", "page", "xerox", "yes", "okay", "cancel", "settings"];
            const isAmbiguous = ambiguousWords.some(w => text === w || text === "print this" || text === "print document");
            if (isAmbiguous) {
                result.intent = 'AMBIGUOUS';
                result.message = "Command unclear. Please specify copies, color mode, or paper size.";
                return result;
            }

            // 15. Unknown fallback
            result.intent = 'UNKNOWN';
            result.message = "Sorry, I can't perform that voice command. Please specify copies, color mode, or paper size.";
            return result;
        }

        /**
         * Debounced speech handling to prevent duplicate rapid executions.
         */
        handleSpeechInput(transcript, confidence) {
            const now = Date.now();
            const normalized = (transcript || "").trim().toLowerCase();

            // Prevent duplicate executions within 1500ms or identical commands within 3000ms
            if ((now - this.lastExecutionTime < 1500) || 
                (normalized === this.lastCommandText && (now - this.lastExecutionTime < 3000))) {
                console.warn("[VOICE] Duplicate speech event ignored:", transcript);
                return;
            }

            this.lastCommandText = normalized;
            this.lastExecutionTime = now;

            const parsed = this.parseCommand(transcript);

            // Log captured speech & intent to server terminal
            sendVoiceTelemetry('SPEECH_CAPTURED', transcript, parsed.intent);

            if (parsed.intent === 'AMBIGUOUS' || parsed.intent === 'UNKNOWN') {
                sendVoiceTelemetry('UNCLEAR', transcript, parsed.intent);
            }

            this.setState('RESULT', parsed);

            if (this.onResultCallback) {
                this.onResultCallback(parsed);
            }
        }
    }

    // Export helpers
    window.AIVoiceAssistant = AIVoiceAssistant;
    window.AIVoiceTelemetry = {
        send: sendVoiceTelemetry,
        speak: speakText
    };

})(window);