"""
Audio transcription module using Groq Whisper Large V3.

Change summary:
- Previously this module used OpenAI Whisper (model="whisper-1").
- We switched to Groq's whisper-large-v3 to avoid the 20MB limit and improve throughput.
- All client initialization and transcription calls now use the Groq SDK.

Note: If your editor shows import errors or odd syntax diagnostics after this change,
it's usually the Python extension needing a refresh. Verify that the 'groq' package
is installed (we added it to backend/requirements.txt) and restart VS Code.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# New OpenAI client import for openai>=1.0
from groq import Groq  # CHANGED: using Groq SDK instead of OpenAI for transcription

# import config if it exists locally
try:
    from config import OPENAI_API_KEY  # type: ignore
    _config_key = OPENAI_API_KEY
except ImportError:
    _config_key = None


def get_groq_key() -> str:
    """Get Groq API key from config.py or environment variable.

    CHANGED: Previously we looked up OPENAI_API_KEY here for Whisper.
    Now we load GROQ_API_KEY for Groq's whisper-large-v3.
    """
    # Try environment variable first
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    # Fallback to config.py at repo root
    config_path = Path(__file__).parent.parent / "config.py"
    if config_path.exists():
        try:
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    with open(config_path, "r", encoding=encoding) as f:
                        content = f.read()
                        if "GROQ_API_KEY" in content:
                            for line in content.splitlines():
                                if line.strip().startswith("GROQ_API_KEY"):
                                    key = line.split("=")[1].strip().strip('"').strip("'")
                                    if key:
                                        return key
                    break
                except UnicodeDecodeError:
                    continue
        except Exception:
            pass
    raise ValueError("Groq API key not found. Set GROQ_API_KEY env var or in config.py")


def transcribe_audio(audio_file_path: str, language: Optional[str] = None) -> dict:
    """Transcribe an audio file using Groq whisper-large-v3.

    CHANGED: Replaced OpenAI Whisper client calls with Groq client calls.
    """
    
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
    
    # CHANGED: Get Groq API key and initialize Groq client
    api_key = get_groq_key()
    client = Groq(api_key=api_key)
    
    print(f"📝 Transcribing: {audio_path.name}")
    print(f" File size: {audio_path.stat().st_size / (1024*1024):.2f} MB")
    print(" Processing... (this may take a minute or two)\n")
    
    try:
        # CHANGED: Send to Groq Whisper Large V3 (model="whisper-large-v3")
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
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
    """Advanced transcription with additional options (Groq).

    CHANGED: This path also uses Groq and the whisper-large-v3 model.
    """
    
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
    
    api_key = get_groq_key()  # CHANGED
    client = Groq(api_key=api_key)  # CHANGED
    
    print(f"📝 Advanced transcription: {audio_path.name}")
    print(f" Format: {response_format} | Language: {language or 'auto'} | Prompt: {'Yes' if prompt else 'No'}\n")
    
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(  # CHANGED
                model="whisper-large-v3",  # CHANGED
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
    main()
