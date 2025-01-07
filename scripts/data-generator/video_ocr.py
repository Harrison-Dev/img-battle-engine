import cv2
import os
import easyocr
import numpy as np
import torch
import csv
from collections import defaultdict

def init_readers():
    """Initialize EasyOCR readers with GPU if available."""
    gpu = torch.cuda.is_available()
    print(f"GPU available: {gpu}")
    # Create two readers: one for Traditional Chinese + English, another for Japanese + English
    ch_reader = easyocr.Reader(['ch_tra', 'en'], gpu=gpu)
    ja_reader = easyocr.Reader(['ja', 'en'], gpu=gpu)
    return ch_reader, ja_reader

def crop_subtitle_region(image):
    """Crop the bottom portion of the frame where subtitles typically appear."""
    height = image.shape[0]
    # Get the bottom 30% of the frame
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

def process_video(video_path, progress_callback=None):
    """Process video and perform OCR on extracted frames."""
    # Initialize OCR readers
    ch_reader, ja_reader = init_readers()
    
    # First, extract frames
    frames_dir = 'frames'
    frame_paths = extract_frames(video_path, frames_dir)
    
    # Process each frame
    results = []
    seen_texts = set()  # Track unique texts
    
    for sec, frame_path in frame_paths:
        texts = perform_ocr(ch_reader, ja_reader, frame_path)
        if texts:
            # Get highest confidence text
            best_text = max(texts, key=lambda x: x['confidence'])
            
            # Skip if we've seen this text before
            if best_text['text'] in seen_texts:
                continue
                
            seen_texts.add(best_text['text'])
            frame_result = {
                'frame': os.path.basename(frame_path),
                'timestamp': sec,
                'texts': texts
            }
            results.append(frame_result)
            
            # Update progress if callback provided
            if progress_callback:
                progress_callback(
                    frame=os.path.basename(frame_path),
                    text=best_text['text'],
                    timestamp=sec
                )
            
            print(f"\nFrame: {os.path.basename(frame_path)} ({sec:.1f}s)")
            for item in texts:
                print(f"Text detected ({item['lang']}): {item['text']} (confidence: {item['confidence']:.2f})")
    
    return results

def save_results(results, base_filename):
    """Save results in both TXT and CSV formats."""
    # Save as TXT
    txt_file = f'{base_filename}.txt'
    with open(txt_file, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(f"Frame: {result['frame']} (Timestamp: {result['timestamp']:.1f}s)\n")
            for item in result['texts']:
                f.write(f"Text ({item['lang']}): {item['text']} (confidence: {item['confidence']:.2f})\n")
            f.write('-' * 50 + '\n')
    
    # Save as CSV
    csv_file = f'{base_filename}.csv'
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Timestamp', 'Frame', 'Language', 'Text', 'Confidence'])
        for result in results:
            for item in result['texts']:
                writer.writerow([
                    f"{result['timestamp']:.1f}",
                    result['frame'],
                    item['lang'],
                    item['text'],
                    f"{item['confidence']:.2f}"
                ])
    
    print(f"\nResults saved to {txt_file} and {csv_file}")
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