import pyaudio
import queue
import logging
from .utils import FORMAT, CHANNELS, RATE, CHUNK
from pydantic import BaseModel


from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional
import pyaudio
import queue
import logging
class AudioPacket(BaseModel):
    """
    Represents a chunk of captured audio data and any
    metadata you need (timestamp, length, etc.).
    """
    audio_data: bytes

class AudioFormat(BaseModel):
    format: int = Field(default=pyaudio.paInt16, description="Audio format (e.g., paInt16)")
    channels: int = Field(default=1, ge=1, description="Number of audio channels")
    rate: int = Field(default=16000, gt=0, description="Sample rate in Hz")
    chunk: int = Field(default=1024, gt=0, description="Frames per buffer")

class ConversationState(BaseModel):
    is_receiving: bool = Field(default=False, description="Whether receiving assistant response")
    def stop_receiving(self) -> None:
        self.is_receiving = False
    def start_receiving(self) -> None:
        self.is_receiving = True
       

class AsyncMicrophone(BaseModel):
    config: AudioFormat = Field(default_factory=AudioFormat)
    conversation_state: ConversationState = Field(default_factory=ConversationState)
    is_recording: bool = Field(default=False, description="Whether the microphone is recording")
    
    # Private attributes for non-serializable components
    _p: pyaudio.PyAudio = PrivateAttr()
    _stream: pyaudio.Stream = PrivateAttr()
    _queue: queue.Queue = PrivateAttr()

    def model_post_init(self, __context) -> None:
        """Initialize PyAudio components after model initialization"""
        self._queue = queue.Queue()
        self._p = pyaudio.PyAudio()
        self._stream = self._p.open(
            format=self.config.format,
            channels=self.config.channels,
            rate=self.config.rate,
            input=True,
            frames_per_buffer=self.config.chunk,
            stream_callback=self.callback,
        )
        logging.info("AsyncMicrophone initialized with config: %s", self.config.model_dump_json())

    def callback(self, in_data, frame_count, time_info, status):
        if self.is_recording and not self.conversation_state.is_receiving:
            self._queue.put(in_data)
        return (None, pyaudio.paContinue)

    def start_recording(self) -> None:
        self.is_recording = True
        logging.info("Started recording. State: %s", self.conversation_state.model_dump_json())

    def stop_recording(self) -> None:
        self.is_recording = False
        logging.info("Stopped recording. State: %s", self.conversation_state.model_dump_json())

    



    def get_audio_data(self) -> Optional[bytes]:
        data = b""
        while not self._queue.empty():
            data += self._queue.get()
        return data if data else None

    def close(self) -> None:
        self._stream.stop_stream()
        self._stream.close()
        self._p.terminate()
        logging.info("AsyncMicrophone closed")

    class Config:
        arbitrary_types_allowed = True