import os
import tempfile
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

whisper = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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
            
        os.remove(temp_audio_path)
        return jsonify({'transcription': transcription['text']})
    
    except Exception as e:
        os.remove(temp_audio_path)
        return jsonify({'error': str(e)}), 500
    
if __name__ == '__main__':
    app.run(debug=True, host='localhost', port=5000)