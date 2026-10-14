"""
Always-On Local Voice Listener for Jarvis.
Captures microphone audio, detects wake-word ('jarvis'),
transcribes commands, dispatches to http://localhost:8000/command,
and speaks responses aloud via pyttsx3.
"""

import re
import sys
import time
import requests
import speech_recognition as sr
import config

try:
    import pyttsx3
    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", 185)
except Exception:
    _tts_engine = None

def _speak(text: str):
    """Speaks text using pyttsx3, stripping Markdown syntax for natural speech."""
    if not _tts_engine:
        print(f"[TTS] {text}")
        return

    # Strip markdown headers, bold, links, code blocks
    clean_text = re.sub(r"```.*?```", "code block omitted", text, flags=re.DOTALL)
    clean_text = re.sub(r"`.*?`", "", clean_text)
    clean_text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", clean_text)
    clean_text = re.sub(r"[#*_~>•]", "", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    # Read the first 2-3 sentences to keep voice responses concise
    sentences = re.split(r"(?<=[.!?])\s+", clean_text)
    spoken_portion = " ".join(sentences[:3])

    print(f"\n🗣️ [Jarvis Voice]: {spoken_portion}")
    try:
        _tts_engine.say(spoken_portion)
        _tts_engine.runAndWait()
    except Exception as e:
        print(f"[!] TTS Speech error: {e}")


def run_voice_listener():
    """Main continuous voice detection loop."""
    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    wake_word = config.WAKE_WORD

    print("=" * 60)
    print("      JARVIS ALWAYS-ON LOCAL ROOM VOICE LISTENER")
    print(f"      Wake Word: '{wake_word}' | Language: '{config.VOICE_LANGUAGE}'")
    print("=" * 60)

    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"\n[!] Could not access system microphone: {e}")
        print("    Ensure PyAudio is installed and your OS has granted microphone permissions.")
        print("    Note: You can still use the 🎙️ Voice Mic button on the Web HUD dashboard!\n")
        sys.exit(1)

    with mic as source:
        print("[*] Calibrating microphone for ambient background noise...")
        recognizer.adjust_for_ambient_noise(source, duration=1.5)
        print("[+] Ready and actively listening. Say 'Jarvis' followed by your command.\n")

    while True:
        try:
            with mic as source:
                audio = recognizer.listen(source, timeout=10, phrase_time_limit=12)

            # Transcribe via Google Speech Recognition API (built into speech_recognition)
            try:
                transcript = recognizer.recognize_google(audio, language=config.VOICE_LANGUAGE).strip()
            except sr.UnknownValueError:
                continue
            except sr.RequestError as req_err:
                print(f"[!] Speech recognition service error: {req_err}")
                continue

            print(f"🎙️ [Heard]: \"{transcript}\"")
            lower_text = transcript.lower()

            if wake_word in lower_text:
                # Extract command after wake word
                parts = lower_text.split(wake_word, 1)
                command = parts[1].strip() if len(parts) > 1 and parts[1].strip() else transcript

                print(f"⚡ [Wake Word Detected!] Command: \"{command}\"")
                _speak("On it, sir.")

                # Dispatch command to FastAPI backend
                endpoint = f"{config.BACKEND_BASE_URL}/command"
                try:
                    res = requests.post(
                        endpoint,
                        json={"command": command, "source": "local_voice"},
                        timeout=60
                    )
                    if res.status_code == 200:
                        data = res.json()
                        reply = data.get("response", "Command finished.")
                        print(f"\n🤖 [Jarvis Answer]:\n{reply}\n")
                        _speak(reply)
                    else:
                        _speak("Backend returned an error.")
                except Exception as net_err:
                    print(f"[!] Connection to Jarvis backend failed: {net_err}")
                    _speak("I could not reach the Jarvis backend server.")

        except sr.WaitTimeoutError:
            continue
        except KeyboardInterrupt:
            print("\n[*] Stopping voice listener...")
            break
        except Exception as err:
            print(f"[!] Error in voice loop: {err}")
            time.sleep(1)

if __name__ == "__main__":
    run_voice_listener()
