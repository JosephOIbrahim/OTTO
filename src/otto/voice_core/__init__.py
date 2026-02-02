"""
OTTO Voice Core Module.

Provides voice processing capabilities for OTTO OS:
- Speech-to-Text (STT) using OpenAI Whisper
- Text-to-Speech (TTS) using OpenAI TTS
- Text preparation for natural speech
- Voice identity management
- Async processing queue with persistence
- Metrics collection

[He2025] Compliance:
- Fixed seeds for all randomness
- Fixed 5-phase pipeline in prepare_for_speech
- Deterministic text normalization
- Batch-invariant processing

Target Metrics:
- Latency: <10 seconds end-to-end
- Cost: ~$0.22/user/day (20 voice interactions)
- Reliability: No message loss (async queue with persistence)
"""

from .determinism import (
    # Seeds
    WHATSAPP_VOICE_SEED,
    TTS_VOICE_SEED,
    STT_NORMALIZATION_SEED,
    COGNITIVE_TILE_SIZE,
    HASH_ALGORITHM,
    # Utilities
    DeterministicRNG,
    compute_checksum,
    verify_determinism,
    kahan_sum,
    batch_invariant_process,
    # Expansion tables
    ABBREVIATION_EXPANSIONS,
    NUMBER_WORDS,
    TENS_WORDS,
)

from .stt import (
    SpeechToText,
    STTConfig,
    TranscriptionResult,
    transcribe_audio,
)

from .tts import (
    TextToSpeech,
    TTSConfig,
    TTSResult,
    TTSVoice,
    TTSModel,
    AudioFormat,
    VOICE_CHARACTERISTICS,
    synthesize_speech,
)

from .prepare_for_speech import (
    prepare_for_speech,
    prepare_chunks_for_speech,
    SpeechText,
)

from .voice_identity import (
    VoiceIdentity,
    VoiceTone,
    SpeakingStyle,
    DEFAULT_IDENTITY,
    adjust_for_context,
    voice_for_emotion,
    # Voice character enforcement
    FORBIDDEN_SPOKEN_PHRASES,
    MAX_SPOKEN_WORDS,
    MAX_SPOKEN_SENTENCES,
    VOICE_RESPONSE_MAX_LENGTH,
    remove_forbidden_phrases,
    limit_for_speech,
    should_respond_with_voice,
    prepare_text_for_voice,
)

from .queue import (
    VoiceProcessingQueue,
    VoiceMessage,
    MessageStatus,
    QueueConfig,
)

from .metrics import (
    VoiceMetricsCollector,
    VoiceMetricsSnapshot,
    LatencyMetrics,
    CostMetrics,
    LatencyTimer,
    get_metrics_collector,
    record_voice_interaction,
)


__all__ = [
    # Determinism
    "WHATSAPP_VOICE_SEED",
    "TTS_VOICE_SEED",
    "STT_NORMALIZATION_SEED",
    "COGNITIVE_TILE_SIZE",
    "HASH_ALGORITHM",
    "DeterministicRNG",
    "compute_checksum",
    "verify_determinism",
    "kahan_sum",
    "batch_invariant_process",
    "ABBREVIATION_EXPANSIONS",
    "NUMBER_WORDS",
    "TENS_WORDS",
    # STT
    "SpeechToText",
    "STTConfig",
    "TranscriptionResult",
    "transcribe_audio",
    # TTS
    "TextToSpeech",
    "TTSConfig",
    "TTSResult",
    "TTSVoice",
    "TTSModel",
    "AudioFormat",
    "VOICE_CHARACTERISTICS",
    "synthesize_speech",
    # Prepare for speech
    "prepare_for_speech",
    "prepare_chunks_for_speech",
    "SpeechText",
    # Voice identity
    "VoiceIdentity",
    "VoiceTone",
    "SpeakingStyle",
    "DEFAULT_IDENTITY",
    "adjust_for_context",
    "voice_for_emotion",
    # Voice character enforcement
    "FORBIDDEN_SPOKEN_PHRASES",
    "MAX_SPOKEN_WORDS",
    "MAX_SPOKEN_SENTENCES",
    "VOICE_RESPONSE_MAX_LENGTH",
    "remove_forbidden_phrases",
    "limit_for_speech",
    "should_respond_with_voice",
    "prepare_text_for_voice",
    # Queue
    "VoiceProcessingQueue",
    "VoiceMessage",
    "MessageStatus",
    "QueueConfig",
    # Metrics
    "VoiceMetricsCollector",
    "VoiceMetricsSnapshot",
    "LatencyMetrics",
    "CostMetrics",
    "LatencyTimer",
    "get_metrics_collector",
    "record_voice_interaction",
]

__version__ = "1.0.0"
