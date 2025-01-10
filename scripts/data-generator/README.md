# Image Battle Data Generator

A tool to generate image data from videos for image battles.

## Features

1. **Video Processing**
   - Download videos from YouTube (single video or playlist)
   - Automatic frame extraction with configurable skip rate
   - Intelligent subtitle region detection (bottom 30% of frame)
   - Real-time processing with pause/resume capability

2. **OCR Processing**
   - Supports Traditional Chinese and Japanese text detection
   - GPU acceleration with CUDA (if available)
   - Configurable confidence threshold
   - Automatic text filtering and deduplication

3. **Web Interface**
   - Modern, user-friendly web UI
   - Real-time processing status and preview
   - Interactive frame gallery with edit capabilities
   - Progress tracking and control features

4. **Frame Management**
   - Edit detected text for individual frames
   - Delete/restore unwanted frames
   - Preview frames in full size
   - Batch operations support

5. **Export Features**
   - CSV export with custom filename
   - Progress-aware downloads
   - Support for partial exports
   - File save dialog with custom location

## Setup

1. Create virtual environment:
```bash
python -m venv venv
source venv/Scripts/activate  # Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## System Requirements

- Python 3.8 or higher
- CUDA-capable GPU (optional, for faster processing)
- Modern web browser
- Sufficient disk space for video processing

## Usage

### Web Interface
1. Start the web server:
```bash
cd scripts/data-generator
python web_ui.py
```

2. Access the interface:
   - Open browser and go to `http://localhost:5000`
   - Enter video URL
   - Configure processing options:
     - Frame Skip Rate (1-30)
     - Confidence Threshold (0.1-1.0)

3. Processing Controls:
   - Start/Stop processing
   - Pause/Resume capability
   - Real-time preview of current frame
   - Progress monitoring

4. Frame Management:
   - View extracted frames in gallery
   - Edit detected text
   - Delete unwanted frames
   - Restore deleted frames
   - Preview frames in full size

5. Export Results:
   - Download complete results
   - Option to download current progress only
   - Custom filename with timestamp
   - Progress tracking during download

## Output Format

The generated CSV contains:
- id: Unique identifier for each entry
- score: Confidence score of OCR detection
- text: Detected text content
- episode: Episode number
- start_time: Timestamp in format MM:SS,mmm
- end_time: End timestamp
- start_frame: Starting frame number
- end_frame: Ending frame number

## File Structure
```
scripts/data-generator/
├── web_ui.py         # Web interface server
├── video_ocr.py      # OCR processing core
├── source_dl.py      # Video download handler
├── main.py           # Command line interface
├── requirements.txt  # Project dependencies
├── templates/        # Web interface templates
├── static/          # Static web resources
├── frames/          # Extracted frame storage
├── downloads/       # Downloaded video storage
└── model_cache/     # OCR model cache
```

## Notes

- Frame skip rate affects processing speed and output density
- Higher confidence threshold means more accurate but fewer results
- GPU acceleration is automatic if CUDA is available
- Temporary files are automatically cleaned up
- Progress can be saved at any point during processing 