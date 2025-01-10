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
from storage import Storage
import subprocess
from pathlib import Path

app = Flask(__name__)
storage = Storage()

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

def process_video_async(video_path, frame_skip=1, confidence_threshold=0.6, start_frame=None):
    """Process video in a separate thread and update progress."""
    global current_progress, processing_event
    try:
        current_progress['status'] = 'processing'
        
        # Initialize OCR and process video
        results = []
        
        # If we have a start frame, we need to skip to that position
        start_frame_number = 0
        if start_frame and start_frame.startswith('frame_'):
            try:
                start_frame_number = int(start_frame.split('_')[1].split('.')[0])
                print(f"Resuming from frame number: {start_frame_number}")
            except:
                print(f"Could not parse start frame number from {start_frame}")
        
        for result in process_video(
            video_path, 
            progress_callback=update_progress, 
            frame_skip=frame_skip,
            confidence_threshold=confidence_threshold,
            pause_event=processing_event,
            start_frame=start_frame_number  # Pass the start frame to process_video
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
    
    # Save progress to storage
    if 'current_url' in current_progress:
        storage.save_job_state(
            current_progress['current_url'],
            current_progress['status'],
            current_progress.get('frame_skip', 8),
            current_progress.get('confidence_threshold', 0.6),
            current_progress
        )
        if frame and text:
            storage.save_frame(
                storage.extract_youtube_id(current_progress['current_url']),
                {
                    'frame': frame,
                    'text': text,
                    'timestamp': timestamp,
                    'confidence': current_progress.get('confidence', 0.6)
                }
            )

def get_ffmpeg_path():
    """Get ffmpeg executable path"""
    # Try to find ffmpeg in common locations
    possible_paths = [
        'ffmpeg',  # If in PATH
        'ffmpeg.exe',
        r'C:\Users\haoc0\Downloads\ffmpeg-7.1-essentials_build\bin\ffmpeg.exe',  # User's FFmpeg location
        r'C:\ffmpeg\bin\ffmpeg.exe',
        os.path.join(os.path.dirname(__file__), 'ffmpeg.exe'),
        os.path.join(os.path.dirname(__file__), 'bin', 'ffmpeg.exe')
    ]
    
    for path in possible_paths:
        try:
            print(f"Trying FFmpeg path: {path}")  # Add debug output
            # Test if ffmpeg is callable
            result = subprocess.run([path, '-version'], 
                                 capture_output=True, 
                                 text=True)
            if result.returncode == 0:
                print(f"Found ffmpeg at: {path}")
                return path
        except Exception as e:
            print(f"Failed to use FFmpeg at {path}: {str(e)}")  # Add error details
            continue
    
    print("FFmpeg not found in common locations")
    return None

def extract_frames_ffmpeg(video_path, frames_info, output_dir='frames', scale_width=640):
    """Extract specific frames using ffmpeg with lower resolution"""
    try:
        print(f"Starting frame extraction from: {video_path}")
        print(f"Output directory: {output_dir}")
        
        # Find ffmpeg
        ffmpeg_path = get_ffmpeg_path()
        if not ffmpeg_path:
            print("Error: FFmpeg not found. Please install FFmpeg and make sure it's in PATH")
            return False
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Verify video file exists
        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return False
        
        # Get video info
        probe = subprocess.run([
            ffmpeg_path, '-i', video_path, 
            '-v', 'quiet', 
            '-print_format', 'json', 
            '-show_format', 
            '-show_streams'
        ], capture_output=True, encoding='utf-8')
        
        print(f"Found {len(frames_info)} frames to extract")
        
        # Extract frames using ffmpeg
        for frame_info in frames_info:
            frame_number = frame_info['frame_number']
            timestamp = frame_info['timestamp']
            
            # Ensure frame number has .jpg extension
            if not frame_number.endswith('.jpg'):
                frame_number = f"{frame_number}.jpg"
            
            output_path = os.path.join(output_dir, frame_number)
            print(f"Extracting frame {frame_number} at timestamp {timestamp} to {output_path}")
            
            try:
                # Use ffmpeg to extract frame at specific timestamp with lower resolution
                result = subprocess.run([
                    ffmpeg_path, '-ss', str(timestamp),
                    '-i', video_path,
                    '-vf', f'scale={scale_width}:-1',  # Scale width to 640px, maintain aspect ratio
                    '-frames:v', '1',
                    '-q:v', '3',  # Lower quality for faster processing
                    '-y',  # Overwrite output file
                    output_path
                ], capture_output=True, encoding='utf-8', errors='ignore')
                
                if result.returncode != 0:
                    print(f"FFmpeg error for frame {frame_number}:")
                    print(f"Command error: {result.stderr}")
            except Exception as e:
                print(f"Error extracting frame {frame_number}: {str(e)}")
                continue
            
        return True
    except Exception as e:
        print(f"Error extracting frames: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

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
    frame_skip = int(data.get('frame_skip', 8))
    confidence_threshold = float(data.get('confidence_threshold', 0.6))
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    try:
        # Check for existing job
        existing_job = storage.get_job_state(url)
        if existing_job and existing_job['job']['status'] != 'completed':
            print(f"Found existing job for URL: {url}")
            
            # Clean up any existing files first
            cleanup_temp_files()
            
            # Create necessary directories
            os.makedirs('frames', exist_ok=True)
            os.makedirs('downloads', exist_ok=True)
            
            # Download video first
            print("Downloading video...")
            download_video(url)
            
            # Get downloaded video path
            downloads_dir = 'downloads'
            video_files = [f for f in os.listdir(downloads_dir) if f.endswith(('.mp4', '.mkv'))]
            if not video_files:
                print("No video file found after download")
                return jsonify({'error': 'No video file found after download'}), 400
            
            video_path = os.path.join(downloads_dir, video_files[0])
            print(f"Video downloaded to: {video_path}")
            
            # Extract frames using ffmpeg
            print("Extracting frames...")
            if extract_frames_ffmpeg(video_path, existing_job['frames']):
                print("Frame extraction completed successfully")
                # Restore previous state
                current_progress.update({
                    'status': 'processing',  # Set to processing to continue
                    'frame': existing_job['job']['current_frame'],
                    'total_frames': existing_job['job']['total_frames'],
                    'processed_frames': existing_job['job']['processed_frames'],
                    'timestamp': existing_job['job']['last_timestamp'],
                    'current_url': url,
                    'frame_skip': existing_job['job']['frame_skip'],
                    'confidence_threshold': existing_job['job']['confidence_threshold']
                })
                
                # Start processing from where we left off
                current_thread = threading.Thread(
                    target=process_video_async,
                    args=(video_path,),
                    kwargs={
                        'frame_skip': existing_job['job']['frame_skip'],
                        'confidence_threshold': existing_job['job']['confidence_threshold'],
                        'start_frame': existing_job['job']['current_frame']  # Pass the last processed frame
                    }
                )
                current_thread.start()
                
                return jsonify({
                    'status': 'restored',
                    'progress': current_progress,
                    'frames': existing_job['frames']
                })
            else:
                print("Frame extraction failed")
                return jsonify({'error': 'Failed to restore frames'}), 500
        
        # Clean up any existing files
        cleanup_temp_files()
        
        # Create necessary directories
        os.makedirs('frames', exist_ok=True)
        os.makedirs('downloads', exist_ok=True)
        
        # Update current progress with URL and parameters
        current_progress['current_url'] = url
        current_progress['frame_skip'] = frame_skip
        current_progress['confidence_threshold'] = confidence_threshold
        
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
    
    if 'current_url' in current_progress:
        storage.cleanup_job(current_progress['current_url'])
    
    current_progress['status'] = 'cancelled'
    is_paused = False
    processing_event.set()  # Resume if paused to allow clean exit
    cleanup_temp_files()
    
    return jsonify({'status': 'cancelled'})

@app.route('/update_frame', methods=['POST'])
def update_frame():
    """Update frame text or deletion status."""
    data = request.json
    frame_number = data.get('frame')
    modified_text = data.get('text')
    is_deleted = data.get('is_deleted')
    
    if 'current_url' in current_progress and frame_number:
        youtube_id = storage.extract_youtube_id(current_progress['current_url'])
        storage.update_frame(youtube_id, frame_number, modified_text, is_deleted)
        return jsonify({'status': 'success'})
    
    return jsonify({'error': 'Invalid request'}), 400

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
        
        # Generate a unique filename with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f'ocr_results_{timestamp}.csv'
        
        # Save to temporary file
        temp_csv = os.path.join('downloads', filename)
        df.to_csv(temp_csv, index=False)
        
        # Create response with file
        response = send_file(
            temp_csv,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
        # Add headers for download progress
        response.headers['Content-Length'] = os.path.getsize(temp_csv)
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        # Clean up temporary file after a delay to ensure download completes
        def cleanup_temp():
            time.sleep(5)  # Wait 5 seconds before cleanup
            if os.path.exists(temp_csv):
                try:
                    os.remove(temp_csv)
                except:
                    pass
        threading.Thread(target=cleanup_temp).start()

# Register cleanup function to run on server shutdown
atexit.register(cleanup_temp_files)

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('frames', exist_ok=True)
    os.makedirs('downloads', exist_ok=True)
    app.run(debug=True) 