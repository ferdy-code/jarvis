SAMPLE_RATE = 16000
BLOCK = 1280  # 80 ms of audio, the size the wake-word model expects


def open_stream():
    """The microphone as 16 kHz mono int16 blocks. Use it in a `with` block."""
    import sounddevice

    return sounddevice.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK
    )
