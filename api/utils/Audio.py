import numpy as np
from typing import Generator

try:
    import sounddevice as sd
    class Audio:
        def __init__(self, chunk: int, channels: int = 1, rate: int = 441000, input_device_index: int = 0, output_device_index: int = 0):
            self._chunk = chunk
            self._channels = channels
            self._rate = rate

            self.stream =  sd.Stream(
			samplerate=rate,
			blocksize=chunk,
			channels=1,
			dtype='int16',
			latency='low',
			device=(input_device_index, output_device_index))


        def listen(self, count: int = None) -> Generator[bytes, None, None]:
            i = 0
            while count is None or i < count:
                try:
                    # Read audio data from input stream
                    audio_data = self.stream.read(self._chunk)
                    yield audio_data
                    i += 1
                except Exception as e:
                    print(f"Error reading audio: {e}")
                    break

        def speak(self, audio_chunk: bytes):
            try:
                self.stream.write(audio_chunk)
            except Exception as e:
                print(f"Error playing audio: {e}")

        def close(self):
            self.stream.stop_stream()
            self.stream.close()
            self._pa.terminate()

        # Context manager support
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()

except ImportError or OSError:
    print("sounddevice is not available. Audio functionality will be disabled.")
    class Audio:
        def __init__(self, *args, **kwargs):
            print("Audio class is not available because sounddevice is not available.")

        def listen(self, count: int = None) -> None:
            print("Audio playback is not available because sounddevice is not available.")

        def speak(self, audio_chunk: bytes):
            print("Audio playback is not available because sounddevice is not available.")
                
        def close(self):
            print("Audio class is not available because sounddevice is not available.")

        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


try:
    import pyrnnoise as nr
    rnn = nr.RNNoise()


    def noise_suppress(audio_data: bytes, sample_rate: int = 48000, channels: int = 2) -> bytes:
        return rnn.process_frame(audio_data, sample_rate=sample_rate, channels=channels)


except ImportError:
    print("pyrnnoise is not available. Noise suppression will be disabled.")
    def noise_suppress(audio_data: bytes, sample_rate: int = 48000, channels: int = 2) -> bytes:
        print("Noise suppression is not available because pyrnnoise is not available.")
        return audio_data


if __name__ == "__main__":
    with Audio(channels=1, chunk=1024, rate=16000) as audio:
        for i, chunk in enumerate(audio.listen(count=5)):
            print(f"Chunk {i+1}: {len(chunk)} samples")
            audio.speak(chunk)
