from flask import Flask, request, jsonify, send_from_directory
import os
import shutil
from parse_sales import run_parsing

app = Flask(__name__, static_url_path='')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.abspath(os.path.join(BASE_DIR, "../../../99_Sbox/売上データ"))

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.csv'):
        filename = file.filename
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        try:
            print(f"Uploaded: {filename}. Running parser...")
            run_parsing()
            return jsonify({"success": True, "message": f"{filename} has been uploaded and processed."})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Only CSV files are allowed"}), 400

if __name__ == '__main__':
    print(f"CRM Server starting at http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
