import os
import argparse
import cv2
import easyocr
import pandas as pd
import torch
from urllib.parse import urlparse, parse_qs
from source_dl import download_playlist, download_video

class ImageBattleGenerator:
    def __init__(self, similarity_threshold=0.4, output_dir='contents'):
        self.similarity_threshold = similarity_threshold
        self.output_dir = os.path.abspath(output_dir)
        # Use GPU if available
        gpu = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {gpu}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA device count: {torch.cuda.device_count()}")
            print(f"CUDA device name: {torch.cuda.get_device_name(0)}")
        # Initialize EasyOCR with Chinese Traditional and English
        self.reader = easyocr.Reader(['ch_tra', 'en'], gpu=gpu == 'cuda')
        
    def compare_frames(self, image1, image2):
        """Compare two frames using template matching."""
        similarity_score = cv2.matchTemplate(image1, image2, cv2.TM_CCOEFF_NORMED)[0][0]
        return similarity_score
    
    def has_subtitle_text(self, frame):
        """Check if frame contains subtitle text."""
        # Convert frame to RGB for better OCR
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Focus on the bottom third of the frame where subtitles usually appear
        height = frame_rgb.shape[0]
        subtitle_region = frame_rgb[height//2:, :]
        
        try:
            result = self.reader.readtext(subtitle_region)
            print(f"OCR result: {result}")  # Debug output
            if result:
                return True, ' '.join([text[1] for text in result])
            return False, ''
        except Exception as e:
            print(f"OCR error: {str(e)}")
            return False, ''
    
    def process_video(self, video_path, series_name):
        """Process a single video file."""
        frames_data = []
        video_name = os.path.basename(video_path)
        episode = video_name.split()[1] if len(video_name.split()) > 1 else '00'
        
        print(f"Processing video: {video_name}")
        print(f"Episode: {episode}")
        
        # Create output directory for frames
        frames_dir = os.path.join(self.output_dir, series_name, f'ep_{episode}')
        os.makedirs(frames_dir, exist_ok=True)
        print(f"Output directory: {frames_dir}")
        
        # Process video frames
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file {video_path}")
            return frames_data
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"FPS: {fps}")
        print(f"Total frames: {total_frames}")
        
        last_saved_frame = None
        last_text = None
        frame_count = 0
        saved_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Calculate timestamp
            timestamp = frame_count / fps
            
            # Check for subtitle text
            has_text, text = self.has_subtitle_text(frame)
            
            if has_text:
                # Only process frame if text is different from last saved text
                if text != last_text:
                    # Save frame
                    frame_path = os.path.join(frames_dir, f'frame_{frame_count:06d}.jpg')
                    cv2.imwrite(frame_path, frame)
                    saved_count += 1
                    
                    # Store frame data with absolute path for storage but relative path for web UI
                    abs_path = os.path.abspath(frame_path)
                    rel_path = os.path.relpath(abs_path, start=self.output_dir)
                    frames_data.append({
                        'image_path': rel_path,
                        'series_name': series_name,
                        'episode': episode,
                        'timestamp': f'{int(timestamp//60):02d}:{int(timestamp%60):02d}',
                        'text': text
                    })
                    
                    last_text = text
                    print(f"Saved frame {frame_count} ({saved_count} total) with text: {text}")
            
            if frame_count % 100 == 0:
                print(f"Processed {frame_count}/{total_frames} frames ({(frame_count/total_frames)*100:.1f}%)")
            
            frame_count += 1
        
        cap.release()
        print(f"Processing completed. Saved {saved_count} frames with text.")
        return frames_data

def main():
    parser = argparse.ArgumentParser(description='Generate image battle data from videos')
    parser.add_argument('--url', required=True, help='YouTube video or playlist URL')
    parser.add_argument('--series', required=True, help='Series name')
    parser.add_argument('--threshold', type=float, default=0.4, help='Frame similarity threshold')
    parser.add_argument('--output', default='contents', help='Output directory')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    
    # Download video(s)
    if 'playlist' in args.url or 'list=' in args.url:
        download_playlist(args.url)
    else:
        download_video(args.url)
    
    # Process videos
    generator = ImageBattleGenerator(
        similarity_threshold=args.threshold,
        output_dir=args.output
    )
    
    all_frames_data = []
    downloads_dir = 'downloads'
    
    for video_file in os.listdir(downloads_dir):
        if video_file.endswith(('.mp4', '.mkv')):
            video_path = os.path.join(downloads_dir, video_file)
            frames_data = generator.process_video(video_path, args.series)
            all_frames_data.extend(frames_data)
    
    # Save to CSV
    if all_frames_data:
        df = pd.DataFrame(all_frames_data)
        csv_path = os.path.join(args.output, f'{args.series}_frames.csv')
        df.to_csv(csv_path, index=False)
        print(f'Generated CSV file: {csv_path}')

if __name__ == '__main__':
    main() 