import cv2
import os
import easyocr
import numpy as np
import torch
import csv
from collections import defaultdict
import base64
import uuid

def init_readers():
    """Initialize EasyOCR readers with GPU if available."""
    gpu = torch.cuda.is_available()
    print(f"GPU available: {gpu}")
    if gpu:
        print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
        # Set CUDA device
        torch.cuda.set_device(0)
    
    # Create readers with CUDA configuration
    reader_config = {
        'gpu': gpu,
        'model_storage_directory': os.path.join(os.path.dirname(__file__), 'model_cache'),
        'download_enabled': True,
        'detector': True,  # Use text detector
        'recognizer': True,  # Use text recognizer
        'verbose': False,  # Reduce console output
        'cudnn_benchmark': True,  # Enable cuDNN benchmarking for better performance
    }
    
    # Create two readers: one for Traditional Chinese + English, another for Japanese + English
    ch_reader = easyocr.Reader(['ch_tra', 'en'], **reader_config)
    ja_reader = easyocr.Reader(['ja', 'en'], **reader_config)
    
    # Warm up the models with a dummy image
    if gpu:
        dummy_image = np.zeros((100, 100, 3), dtype=np.uint8)
        ch_reader.readtext(dummy_image)
        ja_reader.readtext(dummy_image)
        torch.cuda.empty_cache()  # Clear GPU cache after warmup
    
    return ch_reader, ja_reader

def crop_subtitle_region(image):
    """Crop the bottom portion of the frame where subtitles typically appear."""
    height = image.shape[0]
    # Get the bottom 30% of the frame as per design doc
    start_y = int(height * 0.7)
    return image[start_y:height, :]

def extract_frames(video_path, output_dir='frames'):
    """Extract frames from video at regular intervals."""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count/fps
    
    print(f"Video FPS: {fps}")
    print(f"Frame count: {frame_count}")
    print(f"Duration: {duration:.2f} seconds")
    
    # Extract frames more frequently (every 0.5 seconds)
    frames = []
    interval = 0.5  # seconds
    for sec in np.arange(0, duration, interval):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        success, frame = cap.read()
        if success:
            # Crop the frame to subtitle region
            subtitle_region = crop_subtitle_region(frame)
            frame_path = os.path.join(output_dir, f'frame_{int(sec*2):04d}.jpg')
            cv2.imwrite(frame_path, subtitle_region)
            frames.append((sec, frame_path))
            print(f"Extracted frame at {sec:.1f} seconds")
    
    cap.release()
    return frames

def perform_ocr(ch_reader, ja_reader, image_path):
    """Perform OCR on an image using both readers."""
    try:
        # Read image using OpenCV
        image = cv2.imread(image_path)
        
        # Perform OCR with both readers
        ch_results = ch_reader.readtext(image)
        ja_results = ja_reader.readtext(image)
        
        # Extract text and confidence
        texts = []
        
        # Process Chinese results
        for (bbox, text, prob) in ch_results:
            if prob > 0.6:  # Increased confidence threshold
                texts.append({
                    'text': text,
                    'confidence': prob,
                    'bbox': bbox,
                    'lang': 'ch_tra'
                })
        
        # Process Japanese results
        for (bbox, text, prob) in ja_results:
            if prob > 0.6:  # Increased confidence threshold
                texts.append({
                    'text': text,
                    'confidence': prob,
                    'bbox': bbox,
                    'lang': 'ja'
                })
        
        # Sort by confidence
        texts.sort(key=lambda x: x['confidence'], reverse=True)
        
        return texts
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")
        return []

def remove_duplicates(results):
    """Remove duplicate content across frames and select representative frames."""
    # Group frames by content
    content_groups = defaultdict(list)
    for result in results:
        if result['texts']:
            # Use the highest confidence text as the key
            key = result['texts'][0]['text']
            content_groups[key].append(result)
    
    # Select one representative frame from each group
    unique_results = []
    for group in content_groups.values():
        # Sort by confidence and select the frame with highest confidence
        group.sort(key=lambda x: max(t['confidence'] for t in x['texts']), reverse=True)
        unique_results.append(group[0])
    
    # Sort by frame number
    unique_results.sort(key=lambda x: int(x['frame'].split('_')[1].split('.')[0]))
    return unique_results

def process_video(video_path, progress_callback=None, frame_skip=1, confidence_threshold=0.6, pause_event=None):
    """Process video and perform OCR on extracted frames.
    
    Args:
        video_path: Path to the video file
        progress_callback: Optional callback function for progress updates
        frame_skip: Number of frames to skip between processing (default: 1, no skip)
        confidence_threshold: Minimum confidence score for text detection (default: 0.6)
        pause_event: Threading event for pause/resume functionality
    """
    # Initialize OCR readers
    ch_reader, ja_reader = init_readers()
    
    # Enable CUDA optimization
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.enabled = True
    
    # Open video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise Exception(f"Could not open video file: {video_path}")
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    print(f"Video FPS: {fps}")
    print(f"Total frames: {total_frames}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Frame skip: {frame_skip}")
    print(f"Confidence threshold: {confidence_threshold}")
    
    # Create frames directory if needed
    frames_dir = 'frames'
    os.makedirs(frames_dir, exist_ok=True)
    
    # Process frames
    seen_texts = set()  # Track unique texts
    last_text = None
    last_text_frame = 0
    frame_count = 0
    min_text_duration = 0.5  # Minimum duration (in seconds) to consider text as new
    
    # Pre-allocate memory for frame processing
    if torch.cuda.is_available():
        torch.cuda.empty_cache()  # Clear GPU cache before processing
    
    while True:
        # Check for pause if event is provided
        if pause_event:
            pause_event.wait()
            
        ret, frame = cap.read()
        if not ret:
            break
        
        # Skip frames according to frame_skip parameter
        if frame_count % frame_skip != 0:
            frame_count += 1
            continue
        
        timestamp = frame_count / fps
        
        # Only process frame if enough time has passed since last detected text
        if frame_count - last_text_frame > fps * min_text_duration:
            # Crop and process subtitle region
            subtitle_region = crop_subtitle_region(frame)
            
            try:
                # Try Chinese OCR first
                ch_results = ch_reader.readtext(subtitle_region)
                texts = []
                
                # Process Chinese results
                for (bbox, text, prob) in ch_results:
                    if prob > confidence_threshold:
                        texts.append({
                            'text': text,
                            'confidence': prob,
                            'bbox': bbox,
                            'lang': 'ch_tra'
                        })
                
                # If no good Chinese results, try Japanese
                if not texts:
                    ja_results = ja_reader.readtext(subtitle_region)
                    for (bbox, text, prob) in ja_results:
                        if prob > confidence_threshold:
                            texts.append({
                                'text': text,
                                'confidence': prob,
                                'bbox': bbox,
                                'lang': 'ja'
                            })
                
                if texts:
                    # Get highest confidence text
                    best_text = max(texts, key=lambda x: x['confidence'])
                    
                    # Only process if text is different from last one
                    if best_text['text'] != last_text:
                        # Save full frame
                        frame_path = os.path.join(frames_dir, f'frame_{frame_count:06d}.jpg')
                        cv2.imwrite(frame_path, frame)  # Save full frame for context
                        
                        frame_result = {
                            'frame': os.path.basename(frame_path),
                            'timestamp': timestamp,
                            'texts': texts
                        }
                        
                        # Update tracking variables
                        last_text = best_text['text']
                        last_text_frame = frame_count
                        seen_texts.add(last_text)
                        
                        # Update progress if callback provided
                        if progress_callback:
                            progress_callback(
                                frame=os.path.basename(frame_path),
                                text=best_text['text'],
                                timestamp=timestamp,
                                total_frames=total_frames,
                                processed_frames=frame_count
                            )
                        
                        print(f"\nFrame: {os.path.basename(frame_path)} ({timestamp:.1f}s)")
                        print(f"Text detected ({best_text['lang']}): {best_text['text']} (confidence: {best_text['confidence']:.2f})")
                        
                        # Yield result instead of collecting
                        yield frame_result
                
                # Periodically clear GPU cache to prevent memory buildup
                if frame_count % 100 == 0 and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    
            except Exception as e:
                print(f"Error processing frame {frame_count}: {str(e)}")
                continue
        
        if frame_count % 100 == 0:
            print(f"Processed {frame_count}/{total_frames} frames ({(frame_count/total_frames)*100:.1f}%)")
            if progress_callback:
                progress_callback(
                    frame=None,
                    text=None,
                    timestamp=None,
                    total_frames=total_frames,
                    processed_frames=frame_count
                )
        
        frame_count += 1
    
    cap.release()
    
    # Final GPU cleanup
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

def save_results(results, base_filename):
    """Save results in CSV format with required fields."""
    # Convert results to required format
    formatted_results = []
    for i in range(len(results)):
        current = results[i]
        next_result = results[i + 1] if i < len(results) - 1 else None
        
        # Get best text from current frame
        best_text = max(current['texts'], key=lambda x: x['confidence'])
        
        # Generate unique ID
        unique_id = base64.urlsafe_b64encode(uuid.uuid4().bytes).decode('utf-8')[:20]
        
        # Calculate end time/frame
        end_timestamp = next_result['timestamp'] if next_result else current['timestamp'] + 2.0
        current_frame = int(current['frame'].split('_')[1].split('.')[0])
        next_frame = int(next_result['frame'].split('_')[1].split('.')[0]) if next_result else current_frame + 60
        
        formatted_results.append({
            'id': unique_id,
            'score': best_text['confidence'],
            'text': best_text['text'],
            'episode': 1,  # Default episode number
            'start_time': f"{int(current['timestamp']//60):02d}:{int(current['timestamp']%60):02d},{int((current['timestamp']%1)*1000):03d}",
            'end_time': f"{int(end_timestamp//60):02d}:{int(end_timestamp%60):02d},{int((end_timestamp%1)*1000):03d}",
            'start_frame': current_frame,
            'end_frame': next_frame
        })
    
    # Save as CSV
    csv_file = f'{base_filename}.csv'
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'score', 'text', 'episode', 'start_time', 'end_time', 'start_frame', 'end_frame'])
        for result in formatted_results:
            writer.writerow([
                result['id'],
                f"{result['score']:.1f}",
                result['text'],
                result['episode'],
                result['start_time'],
                result['end_time'],
                result['start_frame'],
                result['end_frame']
            ])
    
    print(f"\nResults saved to {csv_file}")
    return csv_file

if __name__ == "__main__":
    # Get the downloaded video file
    downloads_dir = 'downloads'
    video_files = [f for f in os.listdir(downloads_dir) if f.endswith('.mp4')]
    
    if not video_files:
        print("No MP4 files found in downloads directory")
        exit(1)
    
    video_path = os.path.join(downloads_dir, video_files[0])
    print(f"Processing video: {video_path}")
    
    results = process_video(video_path)
    csv_file = save_results(results, 'ocr_results') 