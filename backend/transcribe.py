"""
Audio transcription module using Whisper API. """

import os
import sys
from pathlib import Path
from typing import Optional

<<<<<<< HEAD
# New OpenAI client import for openai>=1.0
=======
>>>>>>> d7b627174a84e7694ea3f5f68207c3842c1ca0b7
from openai import OpenAI

# import config if it exists locally
try:
    from config import OPENAI_API_KEY  # type: ignore
    _config_key = OPENAI_API_KEY
except ImportError:
    _config_key = None


def get_api_key() -> str:
    """Get OpenAI API key from config.py or environment variable.
    
    Priority:
    1. OPENAI_API_KEY from local config.py (ignored by git)
    2. OPENAI_API_KEY environment variable
    
    Returns:
        str: The API key
        
    Raises:
        ValueError: If no API key is found
    """
<<<<<<< HEAD

    api_key = get_api_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not found. Set it in a local config.py or the OPENAI_API_KEY environment variable."
        )

    # Create a new OpenAI client using the correct syntax
    client = OpenAI(api_key=api_key)

    print(f"Transcribing {audio_file_path}...")

    try:
        with open(audio_file_path, "rb") as audio_file:
            #    Correct replacement for the old: (because call has been now updated)
            #    openai.Audio.transcribe("whisper-1", audio_file)
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )

    except FileNotFoundError:
        raise RuntimeError(f"Audio file not found: {audio_file_path}")
    except Exception as e:
        raise RuntimeError(f"Transcription failed: {e}")

    return response.text
=======
    key = _config_key or os.getenv("OPENAI_API_KEY")
    
    if not key:
        raise ValueError(
            "OpenAI API key not found.\n"
            "Set it in one of these ways:\n"
            "  1. Create a local config.py with: OPENAI_API_KEY = 'sk-...'\n"
            "  2. Set environment variable: $env:OPENAI_API_KEY = 'sk-...'\n"
            "Visit https://platform.openai.com/account/api-keys to get a key."
        )
    
    return key
>>>>>>> d7b627174a84e7694ea3f5f68207c3842c1ca0b7


def transcribe_audio(audio_file_path: str, language: Optional[str] = None) -> dict:
    """Transcribe an audio file using OpenAI Whisper.
    
    Args:
        audio_file_path: Path to the audio file (supports mp3, mp4, mpeg, mpga, m4a, wav, webm)
        language: Optional language code (e.g., 'en', 'es', 'fr'). Auto-detected if not provided.
    
    Returns:
        dict: Contains 'text' (transcription), 'language' (detected), and other metadata
    
    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If API key is missing
        Exception: If Whisper API call fails
    """
    # Validate file exists
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    # Get API key
    api_key = get_api_key()
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    print(f"📝 Transcribing: {audio_path.name}")
    print(f" File size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
    print(" Processing... (this may take a minute or two)\n")
    
    try:
        # Open audio file and send to Whisper API
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,  # Optional: specify language for better accuracy
            )
        
        return {
            "text": transcript.text,
            "language": getattr(transcript, "language", "auto-detected"),
            "file": str(audio_path),
            "status": "success"
        }
    
    except Exception as e:
        raise Exception(f"Transcription failed: {str(e)}")


def transcribe_with_options(
    audio_file_path: str,
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    temperature: float = 0,
    response_format: str = "text"
) -> dict:
    """Advanced transcription with additional Whisper options.
    
    Args:
        audio_file_path: Path to audio file
        language: Language code (e.g., 'en', 'es')
        prompt: Optional text to guide the model (e.g., "This is about X-ray physics")
        temperature: Creativity level (0.0 = deterministic, 1.0 = random)
        response_format: 'text', 'json', 'verbose_json', 'srt', 'vtt'
    
    Returns:
        dict: Transcription result with specified format
    """
    audio_path = Path(audio_file_path)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
    
    api_key = get_api_key()
    client = OpenAI(api_key=api_key)
    
    print(f"📝 Advanced transcription: {audio_path.name}")
    print(f" Format: {response_format} | Language: {language or 'auto'} | Prompt: {'Yes' if prompt else 'No'}\n")
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                prompt=prompt,
                temperature=temperature,
                response_format=response_format
            )
        
        # Handle different response formats
        if response_format == "text":
            result_text = transcript.text
        elif response_format == "json":
            result_text = transcript.text
        else:
            result_text = str(transcript)
        
        return {
            "text": result_text,
            "format": response_format,
            "file": str(audio_path),
            "status": "success"
        }
    
    except Exception as e:
        raise Exception(f"Advanced transcription failed: {str(e)}")


def main():
    """CLI entry point for transcribing audio files."""
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <audio_file_path> [language] [prompt]")
        print("\nExamples:")
        print("  python transcribe.py 'tests/audio/audio files/lecture.wav'")
        print("  python transcribe.py 'tests/audio/audio files/lecture.wav' en")
        print("  python transcribe.py 'tests/audio/audio files/lecture.wav' en 'This is about X-ray physics'")
        print("\nSupported audio formats: mp3, mp4, mpeg, mpga, m4a, wav, webm")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else None
    prompt = sys.argv[3] if len(sys.argv) > 3 else None
    
    try:
        if prompt:
            result = transcribe_with_options(audio_file, language=language, prompt=prompt)
        else:
            result = transcribe_audio(audio_file, language=language)
        
        print("✅ Transcription complete!\n")
        print("=" * 80)
        print(result["text"])
        print("=" * 80)
        
        # Save to file
        output_file = Path(audio_file).stem + "_transcript.txt"
        with open(output_file, "w") as f:
            f.write(result["text"])
        print(f"\n💾 Transcript saved to: {output_file}")
    
    except (FileNotFoundError, ValueError) as e:
        print(f" error : {e}")
        sys.exit(1)
    except Exception as e:
        print(f" Transcription error: {e}")
        sys.exit(1)


if __name__ == "__main__":
<<<<<<< HEAD
    _cli()
=======
    main()
>>>>>>> d7b627174a84e7694ea3f5f68207c3842c1ca0b7
