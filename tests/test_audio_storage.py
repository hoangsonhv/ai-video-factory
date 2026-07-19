"""Tests for the audio filesystem storage."""

from __future__ import annotations

import wave
from pathlib import Path

from ai_video_factory.infrastructure.media.audio_storage import AudioStorage
from ai_video_factory.infrastructure.providers.speech.gemini.client import pcm_to_wav


def test_save_writes_named_file_and_creates_dir(tmp_path: Path) -> None:
    storage = AudioStorage(tmp_path / "audio")
    path = storage.save(b"AUDIO")
    assert path.name == "narration.mp3"
    assert path.read_bytes() == b"AUDIO"
    assert storage.directory == tmp_path / "audio"


def test_custom_filename(tmp_path: Path) -> None:
    storage = AudioStorage(tmp_path, filename="voice.wav")
    assert storage.save(b"x").name == "voice.wav"


def test_pcm_to_wav_produces_valid_wav() -> None:
    pcm = b"\x00\x01" * 24000  # 1 second of 16-bit mono at 24 kHz
    wav_bytes = pcm_to_wav(pcm, sample_rate=24000)
    import io

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        assert wav.getframerate() == 24000
        assert wav.getnchannels() == 1
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 24000
