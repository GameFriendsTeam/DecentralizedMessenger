
import numpy as np
from typing import Generator

try:
    import pyaudio
    class Audio:
        def __init__(self, channels: int, chunk: int, rate: int):
            self._channels = channels
            self._chunk = chunk
            self._rate = rate
            
            self._pa = pyaudio.PyAudio()

            # Input stream for listening
            self._listen_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                frames_per_buffer=chunk
            )

            # Output stream for speaking
            self._speak_stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                output=True,
                frames_per_buffer=chunk
            )

        def listen(self, count: int = None) -> Generator[np.ndarray, None, None]:
            """Yield audio chunks from microphone.
            
            Args:
                count: Number of chunks to yield. If None, yields indefinitely.
            
            Yields:
                np.ndarray: Audio data as int16 numpy array
            """
            i = 0
            while count is None or i < count:
                try:
                    # Read audio data from input stream
                    audio_data = self._listen_stream.read(self._chunk, exception_on_overflow=False)
                    yield np.frombuffer(audio_data, dtype=np.int16)
                    i += 1
                except Exception as e:
                    print(f"Error reading audio: {e}")
                    break

        def speak(self, audio_chunk: np.ndarray):
            """Play audio chunk through speakers.
            
            Args:
                audio_chunk: Audio data as numpy array (int16)
            """
            try:
                # Ensure the audio chunk is in the correct format
                if isinstance(audio_chunk, np.ndarray):
                    audio_chunk = audio_chunk.astype(np.int16).tobytes()
                
                self._speak_stream.write(audio_chunk)
            except Exception as e:
                print(f"Error playing audio: {e}")

        def close(self):
            """Clean up resources."""
            self._listen_stream.stop_stream()
            self._listen_stream.close()
            self._speak_stream.stop_stream()
            self._speak_stream.close()
            self._pa.terminate()

        # Context manager support
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
except ImportError:
    print("pyaudio is not available. Audio functionality will be disabled.")
    class Audio:
        def __init__(self, *args, **kwargs):
            print("Audio class is not available because pyaudio is not available.")

        def listen(self, count: int = None) -> None:
            print("Audio playback is not available because pyaudio is not available.")

        def speak(self, audio_chunk: np.ndarray):
            print("Audio playback is not available because pyaudio is not available.")
                
        def close(self):
            print("Audio class is not available because pyaudio is not available.")

        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


# Пример использования
if __name__ == "__main__":
    # Использование как контекстный менеджер (рекомендуется)
    with Audio(channels=1, chunk=1024, rate=16000) as audio:
        # Запись и сразу воспроизведение 5 чанков
        for i, chunk in enumerate(audio.listen(count=5)):
            print(f"Chunk {i+1}: {len(chunk)} samples")
            audio.speak(chunk)
    
    # Или без контекстного менеджера
    # audio = Audio(channels=1, chunk=1024, rate=16000)
    # try:
    #     for chunk in audio.listen(count=10):
    #         audio.speak(chunk)
    # finally:
    #     audio.close()