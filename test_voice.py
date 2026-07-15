from voice_service import (
    transcribe_audio
)

result = transcribe_audio(
    "Recording.m4a"
)

print(result)