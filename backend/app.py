import os
import sys
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
from werkzeug.utils import secure_filename
from openai import OpenAI

# Import note generation functions from our notes module
from notes import generate_structured_notes

# Configuration
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB upload limit

# Get API key from config.py or environment variable
def get_api_key():
    """Get OpenAI API key from config.py file or environment variable."""
    # First try environment variable
    key = os.getenv('OPENAI_API_KEY')
    if key:
        return key
    
    # Try to read from ../config.py
    config_path = Path(__file__).parent.parent / 'config.py'
    if config_path.exists():
        try:
            # Try different encodings
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                try:
                    with open(config_path, 'r', encoding=encoding) as f:
                        content = f.read()
                        # Extract key using simple string parsing
                        if 'OPENAI_API_KEY' in content:
                            for line in content.split('\n'):
                                if line.strip().startswith('OPENAI_API_KEY'):
                                    # Extract the key from quotes
                                    key = line.split('=')[1].strip().strip('"').strip("'")
                                    if key:
                                        print(f"✅ Loaded API key from config.py (encoding: {encoding})")
                                        return key
                    break
                except UnicodeDecodeError:
                    continue
        except Exception as e:
            print(f"Warning: Could not read config.py: {e}")
    
    raise ValueError(
        "OpenAI API key not found. "
        "Set it in ../config.py or OPENAI_API_KEY environment variable."
    )

# Initialize OpenAI client
try:
    client = OpenAI(api_key=get_api_key())
    print("✅ OpenAI client initialized successfully")
except ValueError as e:
    print(f"❌ Error: {e}")
    print("Please create a config.py file with: OPENAI_API_KEY = 'your-key-here'")
    sys.exit(1)

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
    Transcribe an audio file using OpenAI Whisper API.
    Uses temporary files for processing (automatically cleaned up).
    
    Request: multipart/form-data with 'file' field containing audio
    Response: JSON with transcription text and metadata
    """
    # Check if file is present
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
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
        
        # Open and transcribe the audio file using Whisper
        with open(temp_audio_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1"
            )
        
        # Clean up temp file
        os.remove(temp_audio_path)
        
        print(f"✅ Transcription complete!")
        
        return jsonify({
            'status': 'success',
            'filename': secure_filename(file.filename),
            'transcription': transcription.text,
            'language': getattr(transcription, 'language', 'auto-detected')
        }), 200
    
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        
        print(f"❌ Transcription error: {str(e)}")
        return jsonify({'error': f'Transcription failed: {str(e)}'}), 500


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
        
        print(f"Generating {format_type} notes...")
        
        # Generate notes using GPT
        notes = generate_structured_notes(transcript, title, format_type)
        
        return jsonify({
            "status": "success",
            "title": title,
            "format": format_type,
            "notes": notes,
            "transcript_length": len(transcript),
            "word_count": len(transcript.split())
        }), 200
    
    except Exception as e:
        print(f"❌ Note generation error: {str(e)}")
        return jsonify({"error": f"Note generation failed: {str(e)}"}), 500


if __name__ == "__main__":
    print("🚀 Starting Transcrib8 Flask backend...")
    print("📡 Visit http://127.0.0.1:5000/ for API documentation")
    app.run(debug=True, host='127.0.0.1', port=5000)