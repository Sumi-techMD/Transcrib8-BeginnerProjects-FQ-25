import os
import sys
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from werkzeug.utils import secure_filename
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv
import traceback

# Import note generation functions from our notes module
from notes import generate_structured_notes

# Configuration
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB upload limit

# Load environment variables from .env (optional)
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Get API key from config.py or environment variable
def get_api_key():
    """Get OpenAI API key from environment (or .env)."""
    key = os.getenv('OPENAI_API_KEY')
    if key:
        return key
    raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY in environment or .env file.")

# Initialize OpenAI client (for notes)
try:
    client = OpenAI(api_key=get_api_key())
    print("✅ OpenAI client initialized successfully")
except ValueError as e:
    print(f"❌ Error: {e}")
    print("Please create a config.py file with: OPENAI_API_KEY = 'your-key-here'")
    sys.exit(1)

# Initialize Groq client (for transcription)
def get_groq_key() -> str:
    """Get Groq API key from environment (or .env)."""
    key = os.getenv("GROQ_API_KEY")
    if key:
        return key
    raise ValueError("Groq API key not found. Set GROQ_API_KEY in environment or .env file.")

groq_client = Groq(api_key=get_groq_key())
print("✅ Groq client initialized successfully")

# Allowed audio file extensions
ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".wav", ".m4a", ".mpeg", ".mpga", ".webm"}


def allowed_file(filename: str) -> bool:
    #Check if the file extension is allowed
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def home():
    """Home route showing API status and available endpoints."""
    return jsonify({
        "status": "running",
        "version": "2.0",
        "endpoints": {
            "POST /transcribe": "Upload audio file and get transcription",
            "POST /generate-notes": "Generate structured notes from transcript text",
            "GET /": "This help message"
        },
        "audio_formats": list(ALLOWED_EXTENSIONS),
        "max_upload_size_mb": 200
    }), 200


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """
    Transcribe an audio file using Groq's whisper-large-v3 model.
    Uses temporary files for processing (automatically cleaned up).
    
    Request: multipart/form-data with 'file' field containing audio
    Response: JSON with transcription text and metadata
    """
    # Check if file is present
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    # Log request metadata to help diagnose issues
    try:
        print(f"➡️  Request Content-Type: {request.headers.get('Content-Type')}")
        print(f"➡️  Files keys: {list(request.files.keys())}")
        print(f"➡️  Incoming file: name={file.filename}, mimetype={getattr(file, 'mimetype', 'unknown')}")
    except Exception:
        pass
    
    # Check if filename is empty
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check if file extension is allowed
    if not allowed_file(file.filename):
        return jsonify({
            'error': f"File type not allowed. Supported: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400
    
    # Use temporary file for processing (automatically cleaned up)
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name
    
    try:
        print(f"🎙️  Transcribing: {file.filename}")
        # Log basic file info
        try:
            file_size_mb = os.path.getsize(temp_audio_path) / (1024 * 1024)
            print(f"   Size: {file_size_mb:.2f} MB | Ext: {Path(file.filename).suffix}")
        except Exception:
            file_size_mb = None

        # Open and transcribe the audio file using Groq Whisper Large V3
        with open(temp_audio_path, 'rb') as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3"
            )

        # Clean up temp file
        try:
            os.remove(temp_audio_path)
        except Exception:
            pass

        print("✅ Transcription complete!")
        try:
            print(f"   Transcript length: {len(transcription.text)} chars")
        except Exception:
            pass
        return jsonify({
            'status': 'success',
            'filename': secure_filename(file.filename),
            'transcription': transcription.text,
            'language': getattr(transcription, 'language', 'auto-detected')
        }), 200

    except Exception as e:
        # Clean up temp file on error
        try:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
        except Exception:
            pass

        # Provide clearer error messages to the frontend
        msg = str(e)
        err_type = e.__class__.__name__
        tb = traceback.format_exc(limit=3)
        print(f"❌ Transcription error: {err_type}: {msg}\n{tb}")

        # Map common failures to friendly messages
        if "401" in msg or "Unauthorized" in msg:
            friendly = "Groq authentication failed. Check GROQ_API_KEY."
        elif "429" in msg or "rate limit" in msg.lower():
            # Try to extract recommended wait time from the message
            wait_hint = ""
            try:
                # e.g., "Please try again in 4m33s"
                import re
                m = re.search(r"try again in ([0-9]+m[0-9]+s|[0-9]+s)", msg, re.IGNORECASE)
                if m:
                    wait_hint = f" after {m.group(1)}"
            except Exception:
                pass
            friendly = (
                "Groq rate limit reached for whisper-large-v3."
                f" Please retry{wait_hint} or reduce audio length (split the file)."
            )
        elif "413" in msg or "too large" in msg.lower() or "request entity too large" in msg.lower():
            size_part = f" ({file_size_mb:.1f} MB)" if isinstance(file_size_mb, (int, float)) else ""
            friendly = f"File upload failed{size_part}. Large files may timeout during upload. Try: 1) Compress the audio to reduce file size, 2) Convert to MP3 format, or 3) Split into smaller segments."
        elif "model" in msg and "not" in msg and "found" in msg:
            friendly = "Groq model name invalid. Using 'whisper-large-v3'."
        elif "file" in msg and ("not found" in msg or "invalid" in msg):
            friendly = "Uploaded file could not be processed. Try a standard mp3/wav."
        else:
            friendly = "Something went wrong while transcribing. Please try again."

        return jsonify({'error': friendly, 'details': f"{err_type}: {msg}"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Simple health check to verify configuration without exposing secrets."""
    return jsonify({
        "status": "ok",
        "groq_key_present": bool(os.getenv("GROQ_API_KEY")),
        "openai_key_present": bool(os.getenv("OPENAI_API_KEY")),
        "audio_formats": list(ALLOWED_EXTENSIONS),
        "max_upload_size_mb": app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024),
    }), 200


@app.route("/generate-notes", methods=["POST"])
def generate_notes():
    """
    Generate structured notes from transcript text using GPT.
    
    Request JSON:
    {
        "transcript": "The full transcription text...",
        "title": "Optional title for the notes",
        "format": "markdown" (default: markdown, options: markdown, json)
    }
    
    Response: JSON with generated notes
    """
    try:
        # Get JSON data
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        
        transcript = data.get("transcript", "")
        if not transcript or len(transcript.strip()) == 0:
            return jsonify({"error": "Transcript text is required"}), 400
        
        title = data.get("title", "Lecture Notes")
        format_type = data.get("format", "markdown").lower()
        
        if format_type not in ["markdown", "json"]:
            return jsonify({"error": "Format must be 'markdown' or 'json'"}), 400
        
        print(f"📝 Generating {format_type} notes with title: '{title}'...")
        print(f"   Transcript length: {len(transcript)} chars")
        
        # Generate notes using GPT with all parameters from notes.py
        # This function will use MODEL_NAME, MAX_COMPLETION_TOKENS, CHUNK_CHAR_LIMIT from notes.py
        notes = generate_structured_notes(
            transcript=transcript,
            title=title,
            format_type=format_type,
            api_key=None  # Will use get_api_key() from notes.py
        )
        
        print(f"✅ Notes generated successfully! Length: {len(notes)} chars")
        
        return jsonify({
            "status": "success",
            "title": title,
            "format": format_type,
            "notes": notes,
            "transcript_length": len(transcript),
            "word_count": len(transcript.split())
        }), 200
    
    except Exception as e:
        error_msg = str(e)
        error_type = e.__class__.__name__
        print(f"❌ Note generation error ({error_type}): {error_msg}")
        import traceback
        print(traceback.format_exc(limit=3))
        return jsonify({"error": f"Note generation failed: {error_msg}"}), 500


if __name__ == "__main__":
    print("🚀 Starting Transcrib8 Flask backend...")
    print("📡 Visit http://127.0.0.1:5000/ for API documentation")
    app.run(debug=True, host='127.0.0.1', port=5000)
