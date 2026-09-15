import os
import time
import queue
import wave
import numpy as np
import sounddevice as device
import scipy.io.wavfile as wavfile
from groq import Groq
import openwakeword
from openwakeword.model import Model
import glob
import re

# --- CONFIGURATION ---
# Absolute paths to your localized Piper model files
VOICE_ZH = "/home/shaun/pi_assistant/piper_voices/zh_CN-huayan-medium.onnx"
VOICE_EN = "/home/shaun/pi_assistant/piper_voices/ryan.onnx"

SAMPLE_RATE = 16000     # Required by openWakeWord and Whisper
CHUNK_SIZE = 1280       # 80ms chunks for wake word processing
SILENCE_LIMIT = 2.0     # Stop recording after 2 seconds of silence
THRESHOLD = 0.03        # Mic sensitivity for speech loop
# WAKE_WORD = "alexa"     # Native wake word trigger
WAKE_WORD = "hey_wall_e"

# Initialize Groq Client
if "GROQ_API_KEY" not in os.environ:
    raise ValueError("Please set your GROQ_API_KEY environment variable!")
client = Groq()

# Global context memory history supporting bilingual interactions
conversation_history = [
    {
        "role": "system", 
        "content": "You are wall-e, a voice assistant. Respond in the same language the user speaks to you (English or Chinese). Keep replies short (1-2 sentences) so they sound good spoken aloud."
    }
]

audio_queue = queue.Queue()

def audio_callback(indata, frames, time, status):
    """Continuously stream raw mic data to queue."""
    audio_queue.put(indata.copy())

def speak_and_print(text):
    """Cleans up the text by removing <think> tags, selects the correct language, and speaks."""
    # Strip out any <think>...</think> blocks using a non-greedy regular expression
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    if not cleaned_text:
        return

    print(f"\n🤖 Assistant: {cleaned_text}")
    
    # DYNAMIC ENGINE SELECTOR:
    # Checks if the response contains Chinese characters (\u4e00-\u9fff matches Chinese range)
    if re.search(r'[\u4e00-\u9fff]', cleaned_text):
        selected_voice = VOICE_ZH
    else:
        selected_voice = VOICE_EN

    # Escape double quotes safely for the terminal shell pipeline execution
    safe_text = cleaned_text.replace('"', '\\"')
    command = f'echo "{safe_text}" | piper --model {selected_voice} --output-raw | aplay -r 16000 -f S16_LE -t raw 2>/dev/null'
    os.system(command)

def listen_and_record():
    """Triggered after wake word. Records until user stops talking."""
    print("🎙️ Listening...")
    recording = []
    silent_chunks = 0
    has_spoken = False
    
    # Temporarily clear the queue to remove old sound buffers
    while not audio_queue.empty():
        audio_queue.get()

    while True:
        try:
            data = audio_queue.get(timeout=0.1)
            amplitude = np.max(np.abs(data))
            
            if amplitude > THRESHOLD:
                if not has_spoken:
                    has_spoken = True
                recording.append(data)
                silent_chunks = 0
            elif has_spoken:
                recording.append(data)
                silent_chunks += 1
                
            if has_spoken and (silent_chunks * 0.08) > SILENCE_LIMIT:
                break
        except queue.Empty:
            continue

    audio_data = np.concatenate(recording, axis=0)
    filename = "temp_input.wav"
    wavfile.write(filename, SAMPLE_RATE, (audio_data * 32767).astype(np.int16))
    return filename

def main():
    print(f"📦 Loading wake word model: {WAKE_WORD}")
    
    # 1. Locate the true internal path for your selected model name
    base_dir = os.path.dirname(openwakeword.__file__)
    model_search = os.path.join(base_dir, "resources", "models", f"*{WAKE_WORD}*.onnx")
    found_files = glob.glob(model_search)

    if not found_files:
        raise ValueError(f"Could not automatically locate the ONNX file for wake word: {WAKE_WORD}")
        
    target_onnx_path = found_files
    print(f"📦 Successfully mapped wake word path: {target_onnx_path}")

    # 2. Instantiate openwakeword using the direct unnested list variable path
    oww_model = Model(
        wakeword_model_paths=target_onnx_path
    )
    
    print("\n✨ Assistant Active!")
    speak_and_print("System online. Ready for your command.")
    print(f"💤 Waiting for you to say '{WAKE_WORD}'...")
    
    # Start microphone stream globally
    stream = device.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=CHUNK_SIZE, callback=audio_callback)
    with stream:
        while True:
            try:
                # Get audio slice from queue
                chunk = audio_queue.get()
                audio_int16 = (chunk * 32767).astype(np.int16).flatten()
                
                # Get prediction dictionary
                prediction = oww_model.predict(audio_int16)
                
                # Safely parse score using key checking to avoid KeyError
                score = 0.0
                for key, value in prediction.items():
                    if WAKE_WORD in key:
                        score = value
                        break
                
                # Trigger if the wake word confidence score passes our 0.5 threshold
                if score > 0.3:
                    print(f"\n🔔 Wake word '{WAKE_WORD}' detected! [score:{score}]")
                    speak_and_print("Yes?")
                    
                    # 2. Record User Speech via VAD
                    audio_file = listen_and_record()
                    
                    # 3. Transcribe with Groq Cloud (Auto-detects language for English/Chinese)
                    print("🔀 Transcribing...")
                    with open(audio_file, "rb") as file:
                        transcription = client.audio.transcriptions.create(
                            file=(audio_file, file.read()),
                            model="whisper-large-v3"
                        )
                    
                    user_text = transcription.text.strip()
                    if os.path.exists(audio_file):
                        os.remove(audio_file)
                        
                    if not user_text:
                        print("⚠️ Heard nothing.")
                        print(f"\n💤 Waiting for '{WAKE_WORD}'...")
                        continue
                        
                    print(f"👤 You: {user_text}")
                    print("🧠 Thinking...")
                    
                    # 4. Process with Memory/Context using openai/gpt-oss-120b
                    conversation_history.append({"role": "user", "content": user_text})
                    
                    chat_completion = client.chat.completions.create(
                        messages=conversation_history,
                        model="openai/gpt-oss-120b",
                    )
                    
                    # Correct structure lookup for choices index 0
                    reply = chat_completion.choices[0].message.content
                    conversation_history.append({"role": "assistant", "content": reply})
                    
                    # Keep memory array short (limit to last 6 messages to keep API fast)
                    if len(conversation_history) > 7:
                        conversation_history.pop(1)
                        conversation_history.pop(1)
                    
                    # 5. Output Response to text log AND play audio
                    speak_and_print(reply)
                    print(f"\n💤 Waiting for '{WAKE_WORD}'...")
                    
            except KeyboardInterrupt:
                print("\nShutting down. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    main()

