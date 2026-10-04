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

    class AIVoiceAssistant {
        constructor() {
            this.recognition = null;
            this.isListening = false;
            this.state = 'READY'; // READY, LISTENING, PROCESSING, RESULT, ERROR
            this.onStateChangeCallback = null;
            this.onResultCallback = null;
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
            };

            this.recognition.onresult = (event) => {
                this.setState('PROCESSING');
                // Ensure mic is stopped immediately
                this.stopListening();

                if (event.results && event.results.length > 0) {
                    const transcript = event.results[0][0].transcript.trim();
                    const confidence = event.results[0][0].confidence;
                    this.handleSpeechInput(transcript, confidence);
                } else {
                    this.setState('READY');
                }
            };

            this.recognition.onerror = (event) => {
                console.warn("Speech recognition error:", event.error);
                this.stopListening();
                this.setState('ERROR', event.error === 'not-allowed' 
                    ? "Microphone access denied. Please grant permission."
                    : `Voice error: ${event.error}`);
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
         */
        parseCommand(rawText) {
            const text = rawText.toLowerCase();
            const result = {
                raw: rawText,
                intent: 'CONFIGURE_PRINT', // CONFIGURE_PRINT, PREVIEW, NAVIGATION, UNKNOWN
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

            // 1. Navigation / Role-gated actions
            if (text.includes("open dashboard") || text.includes("show dashboard") || text.includes("owner settings")) {
                result.intent = 'NAVIGATION';
                result.navigationTarget = 'DASHBOARD';
                result.message = "Role Restricted: Dashboard navigation requires shop owner authentication.";
                return result;
            }

            if (text.includes("preview") || text.includes("show my file") || text.includes("view document")) {
                result.intent = 'PREVIEW';
                return result;
            }

            if (text.includes("show price") || text.includes("order summary") || text.includes("checkout")) {
                result.intent = 'SUMMARY';
                return result;
            }

            if (text.includes("show status") || text.includes("track order") || text.includes("order status")) {
                result.intent = 'STATUS';
                return result;
            }

            // 2. Identify target file index
            const fileMatch = text.match(/(?:file|document|doc)\s*(\d+|one|two|three|four|five|first|second|third)/i);
            if (fileMatch) {
                const rawNum = fileMatch[1].toLowerCase();
                result.targetFile = WORD_TO_NUMBER[rawNum] || parseInt(rawNum) || 1;
            }

            // 3. Extract Copies
            const copiesMatch = text.match(/(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*cop(?:y|ies)/i);
            if (copiesMatch) {
                const cVal = copiesMatch[1].toLowerCase();
                result.copies = WORD_TO_NUMBER[cVal] || parseInt(cVal) || 1;
            } else {
                const numMatch = text.match(/\b(\d+)\s*(?:print|pages?)/i);
                if (numMatch) result.copies = parseInt(numMatch[1]);
            }

            // 4. Extract Color Mode
            if (text.includes("color") || text.includes("full color") || text.includes("colour")) {
                result.printType = "COLOR";
            } else if (text.includes("black and white") || text.includes("b and w") || text.includes("b&w") || text.includes("grayscale") || text.includes("monochrome") || text.includes("bw")) {
                result.printType = "BW";
            } else if (text.includes("mixed")) {
                result.printType = "MIXED";
            }

            // 5. Extract Duplex / Sides
            if (text.includes("double-sided") || text.includes("double sided") || text.includes("duplex") || text.includes("two-sided") || text.includes("both sides") || text.includes("2-sided")) {
                result.duplex = true;
            } else if (text.includes("single-sided") || text.includes("single sided") || text.includes("1-sided") || text.includes("one-sided") || text.includes("front only")) {
                result.duplex = false;
            }

            // 6. Extract Paper Size
            if (text.includes("a3")) {
                result.paperSize = "A3";
            } else if (text.includes("legal")) {
                result.paperSize = "LEGAL";
            } else if (text.includes("a4")) {
                result.paperSize = "A4";
            }

            // 7. Extract Finishing Services
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

            // 8. Extract Page Range
            const rangeMatch = text.match(/pages?\s*(\d+\s*(?:to|-)\s*\d+|\d+)/i);
            if (rangeMatch) {
                result.pageRanges = rangeMatch[1].replace(/\s*to\s*/i, "-");
            }

            // Check if any recognized settings exist
            const hasSettings = result.copies !== null || result.printType !== null || 
                                result.duplex !== null || result.paperSize !== null || 
                                result.finishingService !== null || result.pageRanges !== null;

            if (!hasSettings) {
                result.intent = 'UNKNOWN';
                result.message = "Sorry, I can't perform that voice command.";
            }

            return result;
        }

        handleSpeechInput(transcript, confidence) {
            const parsed = this.parseCommand(transcript);
            this.setState('RESULT', parsed);

            if (this.onResultCallback) {
                this.onResultCallback(parsed);
            }
        }
    }

    // Export globally
    window.AIVoiceAssistant = AIVoiceAssistant;

})(window);
