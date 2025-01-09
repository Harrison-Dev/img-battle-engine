from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
import shutil
from source_dl import download_video
from video_ocr import process_video, save_results
import pandas as pd
import threading
import queue
import atexit
import time

app = Flask(__name__)

# Global variables for progress tracking
current_progress = {
    'status': 'idle',
    'frame': None,
    'text': None,
    'timestamp': None,
    'total_frames': 0,
    'processed_frames': 0
}
processing_queue = queue.Queue()
current_thread = None
is_paused = False
processing_event = threading.Event()
processing_event.set()  # Initially not paused

def cleanup_temp_files():
    """Clean up temporary files and directories."""
    try:
        # Clean up frames directory
        if os.path.exists('frames'):
            shutil.rmtree('frames')
        # Clean up downloads directory
        if os.path.exists('downloads'):
            shutil.rmtree('downloads')
        # Remove results file
        if os.path.exists('ocr_results.csv'):
            os.remove('ocr_results.csv')
    except Exception as e:
        print(f"Error during cleanup: {str(e)}")

def process_video_async(video_path, frame_skip=1, confidence_threshold=0.6):
    """Process video in a separate thread and update progress."""
    global current_progress, processing_event
    try:
        current_progress['status'] = 'processing'
        
        # Initialize OCR and process video
        results = []
        for result in process_video(
            video_path, 
            progress_callback=update_progress, 
            frame_skip=frame_skip,
            confidence_threshold=confidence_threshold,
            pause_event=processing_event
        ):
            results.append(result)
            # Check if processing should be paused
            processing_event.wait()
            
            if current_progress['status'] == 'cancelled':
                break
        
        if current_progress['status'] != 'cancelled':
            # Save results
            csv_file = save_results(results, 'ocr_results')
            current_progress['status'] = 'completed'
        
        return results
    except Exception as e:
        current_progress['status'] = 'error'
        print(f"Error processing video: {str(e)}")
        raise

def update_progress(frame, text, timestamp, total_frames=None, processed_frames=None):
    """Callback function to update processing progress."""
    global current_progress
    current_progress['frame'] = frame
    current_progress['text'] = text
    current_progress['timestamp'] = timestamp
    if total_frames is not None:
        current_progress['total_frames'] = total_frames
    if processed_frames is not None:
        current_progress['processed_frames'] = processed_frames

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pause', methods=['POST'])
def pause_processing():
    """Pause the current processing job."""
    global is_paused, processing_event
    is_paused = True
    processing_event.clear()
    return jsonify({'status': 'paused'})

@app.route('/resume', methods=['POST'])
def resume_processing():
    """Resume the current processing job."""
    global is_paused, processing_event
    is_paused = False
    processing_event.set()
    return jsonify({'status': 'resumed'})

@app.route('/download', methods=['POST'])
def download():
    global current_thread, current_progress
    
    data = request.json
    url = data.get('url')
    frame_skip = int(data.get('frame_skip', 1))
    confidence_threshold = float(data.get('confidence_threshold', 0.6))
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # Clean up any existing files
        cleanup_temp_files()
        
        # Create necessary directories
        os.makedirs('frames', exist_ok=True)
        os.makedirs('downloads', exist_ok=True)
        
        # Download video
        download_video(url)
        
        # Get downloaded video path
        downloads_dir = 'downloads'
        video_files = [f for f in os.listdir(downloads_dir) if f.endswith(('.mp4', '.mkv'))]
        if not video_files:
            return jsonify({'error': 'No video file found after download'}), 400
        
        video_path = os.path.join(downloads_dir, video_files[0])
        
        # Reset processing state
        global is_paused, processing_event
        is_paused = False
        processing_event.set()
        
        # Start processing in background thread
        current_thread = threading.Thread(
            target=process_video_async,
            args=(video_path,),
            kwargs={
                'frame_skip': frame_skip,
                'confidence_threshold': confidence_threshold
            }
        )
        current_thread.start()
        
        return jsonify({'status': 'processing'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cancel', methods=['POST'])
def cancel_processing():
    """Cancel the current processing job and clean up."""
    global current_progress, current_thread, is_paused, processing_event
    
    current_progress['status'] = 'cancelled'
    is_paused = False
    processing_event.set()  # Resume if paused to allow clean exit
    cleanup_temp_files()
    
    return jsonify({'status': 'cancelled'})

@app.route('/progress')
def progress():
    progress_data = current_progress.copy()
    progress_data['is_paused'] = is_paused
    return jsonify(progress_data)

@app.route('/frames/<path:filename>')
def serve_frame(filename):
    return send_from_directory('frames', filename)

@app.route('/download_csv', methods=['POST'])
def download_csv():
    """Download the results CSV file with modifications."""
    try:
        data = request.json
        deleted_frames = set(data.get('deleted_frames', []))
        modified_texts = data.get('modified_texts', {})
        current_only = data.get('current_only', False)
        
        # Read the original CSV
        df = pd.read_csv('ocr_results.csv')
        
        if current_only:
            # Only include frames up to the current processed frame
            max_frame = current_progress.get('processed_frames', 0)
            df = df[df['start_frame'] <= max_frame]
        
        # Remove deleted frames
        df = df[~df['start_frame'].astype(str).isin(deleted_frames)]
        
        # Update modified texts
        for frame, new_text in modified_texts.items():
            frame_idx = df['start_frame'].astype(str) == frame
            if any(frame_idx):
                df.loc[frame_idx, 'text'] = new_text
        
        # Save to temporary file
        temp_csv = 'modified_results.csv'
        df.to_csv(temp_csv, index=False)
        
        # Send file
        return send_file(temp_csv,
                        mimetype='text/csv',
                        as_attachment=True,
                        download_name='ocr_results.csv')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temporary file
        if os.path.exists('modified_results.csv'):
            os.remove('modified_results.csv')

# Register cleanup function to run on server shutdown
atexit.register(cleanup_temp_files)

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('frames', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True) 