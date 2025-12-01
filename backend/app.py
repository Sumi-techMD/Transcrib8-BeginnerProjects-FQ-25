import os
import tempfile
from flask import Flask, request, jsonify
from openai import OpenAI

# Serve static files (index.html, script.js, styles.css) from THIS folder
app = Flask(__name__, static_folder=".", static_url_path="")

# Load API key from config.py or env
try:
    from config import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

whisper = OpenAI(api_key=OPENAI_API_KEY)


@app.route("/")
def index():
    """
    When you go to http://127.0.0.1:5000/ or http://localhost:5000/,
    this route returns index.html from the current folder.
    """
    return app.send_static_file("index.html")


@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    with tempfile.NamedTemporaryFile(delete=False) as temp_audio:
        file.save(temp_audio.name)
        temp_audio_path = temp_audio.name
        
    try:
        with open(temp_audio_path, 'rb') as audio_file:
            transcription = whisper.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1"
            )
            
        transcript_text = transcription.text
        return jsonify({'transcription': transcript_text})
    
    except Exception as e:
        print("Transcription error:", repr(e)) # prints the error
        return jsonify({'error': str(e)}), 500
    
    finally:
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)
