from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
from source_dl import download_video
from video_ocr import process_video, save_results
import pandas as pd
import threading
import queue

app = Flask(__name__)

# Global variables for progress tracking
current_progress = {
    'status': 'idle',
    'frame': None,
    'text': None,
    'timestamp': None
}
processing_queue = queue.Queue()

def process_video_async(video_path):
    """Process video in a separate thread and update progress."""
    global current_progress
    try:
        current_progress['status'] = 'processing'
        
        # Initialize OCR and process video
        results = process_video(video_path, progress_callback=update_progress)
        
        # Save results
        csv_file = save_results(results, 'ocr_results')
        
        current_progress['status'] = 'completed'
        return results
    except Exception as e:
        current_progress['status'] = 'error'
        print(f"Error processing video: {str(e)}")
        raise

def update_progress(frame, text, timestamp):
    """Callback function to update processing progress."""
    global current_progress
    current_progress['frame'] = frame
    current_progress['text'] = text
    current_progress['timestamp'] = timestamp

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # Download video
        download_video(url)
        return jsonify({'message': 'Video downloaded successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/process', methods=['POST'])
def process():
    try:
        # Get the downloaded video file
        downloads_dir = 'downloads'
        video_files = [f for f in os.listdir(downloads_dir) if f.endswith('.mp4')]
        
        if not video_files:
            return jsonify({'error': 'No video file found'}), 404
        
        video_path = os.path.join(downloads_dir, video_files[0])
        
        # Start processing in a separate thread
        thread = threading.Thread(target=process_video_async, args=(video_path,))
        thread.start()
        
        return jsonify({'message': 'Processing started'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/progress')
def get_progress():
    """Get current processing progress."""
    return jsonify(current_progress)

@app.route('/frames/<path:filename>')
def serve_frame(filename):
    """Serve frame images."""
    return send_from_directory('frames', filename)

@app.route('/download_csv')
def download_csv():
    """Download the results CSV file."""
    try:
        return send_file('ocr_results.csv',
                        mimetype='text/csv',
                        as_attachment=True,
                        download_name='ocr_results.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('frames', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True) 