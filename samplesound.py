import numpy as np
import wave

sample_rate = 44100
duration = 2  # seconds

# Start with silence
audio = np.zeros(int(sample_rate * duration), dtype=np.int16)

# Add a short pulse (click)
audio[1000:1100] = 30000   # small spike
audio[20000:20100] = -30000  # another spike

with wave.open("click_sound.wav", "wb") as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(sample_rate)
    f.writeframes(audio.tobytes())

print("Click sound file created")