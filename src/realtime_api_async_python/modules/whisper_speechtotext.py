
import asyncio 
import logging
from .utils import base64_encode_audio
import whisper 
from .logging import logger, log_ws_event
import torch
import numpy as np

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')



async def transcribe_audio(audio_data:bytes):
    # Load the Whisper model
    audio_array = np.frombuffer(audio_data, dtype=np.int16)

    # Normalize the array to the range [-1, 1]
    audio_array = audio_array.astype(np.float32) / 32768.0
    model = whisper.load_model("large-v3", device=device)
    # Transcribe the audio with the language set to English
    result = model.transcribe(audio_array, language='en')
    print(f"********************************************* \nTranscription: {result}")
    return result
                
