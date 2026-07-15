import logging
import re

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

logger = logging.getLogger("clinical-intelligence-api.voice")

SAMPLE_RATE = 16000
MIN_AUDIO_DURATION_SECONDS = 0.75
SUSPICIOUS_TRANSCRIPTS = {"...", "... ...", "... ... ..."}
SUPPORTED_LANGUAGES = {"en", "hi", "bn"}

# -----------------------------------
# LOAD WHISPER MODEL
# -----------------------------------

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
)


# -----------------------------------
# TRANSCRIBE AUDIO
# -----------------------------------

def _normalize_language(language):
    language_code = (language or "").strip().lower()
    if not language_code:
        return None

    if language_code not in SUPPORTED_LANGUAGES:
        logger.warning(
            "Unsupported voice language=%r; falling back to Whisper auto-detection",
            language,
        )
        return None

    return language_code


def _clean_transcript(transcription):
    cleaned = transcription.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"([.!?,])\1+", r"\1", cleaned)
    cleaned = re.sub(r"\s+([.!?,])", r"\1", cleaned)
    return cleaned.strip()


def _mean_metric(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def transcribe_audio(audio_path, language=None):
    selected_language = _normalize_language(language)
    audio = decode_audio(audio_path, sampling_rate=SAMPLE_RATE)
    duration_seconds = len(audio) / SAMPLE_RATE if len(audio) else 0
    peak_amplitude = float(abs(audio).max()) if len(audio) else 0
    mean_amplitude = float(abs(audio).mean()) if len(audio) else 0

    logger.info(
        "Voice audio decoded: path=%s duration=%.2fs samples=%s peak=%.5f mean=%.5f selected_language=%s",
        audio_path,
        duration_seconds,
        len(audio),
        peak_amplitude,
        mean_amplitude,
        selected_language or "auto",
    )

    if duration_seconds < MIN_AUDIO_DURATION_SECONDS:
        logger.warning(
            "Voice audio too short for reliable transcription: duration=%.2fs",
            duration_seconds,
        )
        return ""

    segments, info = model.transcribe(
        audio,
        language=selected_language,
        beam_size=5,
        best_of=5,
        temperature=0,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    logger.info(
        "Whisper language diagnostics: selected=%s detected=%s probability=%.3f duration=%.2fs",
        selected_language or "auto",
        getattr(info, "language", None),
        getattr(info, "language_probability", 0),
        getattr(info, "duration", duration_seconds),
    )

    segment_texts = []
    avg_logprobs = []
    no_speech_probs = []
    compression_ratios = []

    for segment in segments:
        text = segment.text.strip()
        avg_logprob = getattr(segment, "avg_logprob", None)
        no_speech_prob = getattr(segment, "no_speech_prob", None)
        compression_ratio = getattr(segment, "compression_ratio", None)
        avg_logprobs.append(avg_logprob)
        no_speech_probs.append(no_speech_prob)
        compression_ratios.append(compression_ratio)

        logger.info(
            "Whisper segment: start=%.2f end=%.2f avg_logprob=%s no_speech_prob=%s compression_ratio=%s text=%r",
            segment.start,
            segment.end,
            avg_logprob,
            no_speech_prob,
            compression_ratio,
            text,
        )
        if text:
            segment_texts.append(text)

    raw_transcription = " ".join(segment_texts).strip()
    transcription = _clean_transcript(raw_transcription)

    logger.info(
        "Whisper confidence metrics: avg_logprob=%s no_speech_prob=%s compression_ratio=%s raw=%r cleaned=%r",
        _mean_metric(avg_logprobs),
        _mean_metric(no_speech_probs),
        _mean_metric(compression_ratios),
        raw_transcription,
        transcription,
    )

    if raw_transcription in SUSPICIOUS_TRANSCRIPTS or transcription in SUSPICIOUS_TRANSCRIPTS:
        logger.warning(
            "Discarding suspicious voice transcription: %r",
            raw_transcription,
        )
        return ""

    return transcription
