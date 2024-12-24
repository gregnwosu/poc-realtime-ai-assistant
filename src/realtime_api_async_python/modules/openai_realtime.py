from .logging import logger, log_ws_event
from .utils import base64_encode_audio
import asyncjson
from .utils import (
    RUN_TIME_TABLE_LOG_JSON,
    SESSION_INSTRUCTIONS,
    PREFIX_PADDING_MS,
    SILENCE_THRESHOLD,
    SILENCE_DURATION_MS,
)
from .tools import (
    tools,
)


def get_openai_send_audio_callback(websocket):    
    async def send_audio(audio_data):
        base64_audio = base64_encode_audio(audio_data)
        if base64_audio:
            audio_event = {
                "type": "input_audio_buffer.append",
                "audio": base64_audio,
            }
            log_ws_event("Outgoing", audio_event)
            await websocket.send(await asyncjson.dumps(audio_event))
        else:
            logger.debug("No audio data to send")
    return send_audio
    
def get_openai_after_recieve_callback(websocket):
    async def close_websocket():
        await websocket.close()
    return close_websocket


async def initialize_session(websocket):
    session_update = {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": SESSION_INSTRUCTIONS,
            "voice": "alloy",
            "input_audio_format": "pcm16",
            "output_audio_format": "pcm16",
            "turn_detection": {
                "type": "server_vad",
                "threshold": SILENCE_THRESHOLD,
                "prefix_padding_ms": PREFIX_PADDING_MS,
                "silence_duration_ms": SILENCE_DURATION_MS,
            },
            "tools": tools,
        },
    }
    log_ws_event("Outgoing", session_update)
    await websocket.send(await asyncjson.dumps(session_update))