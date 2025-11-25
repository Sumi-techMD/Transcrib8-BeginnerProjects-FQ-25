import os
import sys
from typing import Optional

import openai

try:
    # Prefer config.py if present (local, ignored file)
    from config import OPENAI_API_KEY  # type: ignore
except Exception:
    OPENAI_API_KEY = None


def get_api_key() -> Optional[str]:
    """Return the OpenAI API key from config or environment.

    Order of preference:
    1. `OPENAI_API_KEY` variable from a local `config.py` (not committed)
    2. `OPENAI_API_KEY` environment variable
    """
    if OPENAI_API_KEY:
        return OPENAI_API_KEY
    return os.getenv("OPENAI_API_KEY")


def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe an audio file using OpenAI Whisper and return the text.

    Raises:
        RuntimeError: if API key is missing or request fails.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Set it in a local config.py or the OPENAI_API_KEY environment variable."
        )

    openai.api_key = api_key

    print(f"Transcribing {audio_file_path}...")
    try:
        with open(audio_file_path, "rb") as audio_file:
            # Uses the OpenAI python client to call Whisper (model name may vary)
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
    except FileNotFoundError:
        raise RuntimeError(f"Audio file not found: {audio_file_path}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")

    # The library returns an object with a .text attribute in many wrappers
    # Fall back to str() if not available.
    return getattr(transcript, "text", str(transcript))


def _cli() -> None:
    """Simple CLI / test harness.

    Usage:
        python transcribe.py <audio_file_path>

    If no path is provided, the function will print usage instructions.
    """
    if len(sys.argv) > 1:
        path = sys.argv[1]
        try:
            result = transcribe_audio(path)
            print("\nTranscript:")
            print(result)
        except RuntimeError as err:
            print(f"Error: {err}")
            sys.exit(1)
    else:
        print("Usage: python transcribe.py <audio_file_path>")


if __name__ == "__main__":
    _cli()