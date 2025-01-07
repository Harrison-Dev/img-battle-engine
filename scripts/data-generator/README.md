# Image Battle Data Generator

A tool to generate image data from videos for image battles.

## Features

1. **Video Download**
   - Download videos from YouTube (single video or playlist)
   - Organize downloads into series-specific folders
   - Supports both single video links and playlist URLs

2. **Frame Extraction**
   - Intelligent frame extraction from videos
   - Removes similar/duplicate frames
   - Configurable similarity threshold
   - Maintains high-quality frame output

3. **Text Detection**
   - OCR processing for subtitle detection
   - Supports Traditional Chinese text
   - Filters frames based on text presence
   - Uses EasyOCR for text detection

4. **Data Organization**
   - Generates CSV file in the required format
   - Compatible with existing battle system
   - Includes metadata and frame information

5. **Web Interface**
   - Easy-to-use web UI for job submission
   - Real-time job status monitoring
   - Progress tracking for long-running tasks
   - No command line knowledge required

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

## Usage

### Web Interface (Recommended)
1. Start the web server:
```bash
python web_ui.py
```
2. Open your browser and go to `http://localhost:5000`
3. Fill in the form with:
   - YouTube URL (video or playlist)
   - Series name
   - Optional: similarity threshold and output directory
4. Click "Start Processing" and monitor the progress

### Command Line
```bash
python main.py --url <youtube_url> --series <series_name>
```

Optional arguments:
- `--url`: YouTube video or playlist URL
- `--series`: Name of the series (for folder organization)
- `--threshold`: Similarity threshold for frame comparison (default: 0.4)
- `--output`: Custom output directory

## Output Format

The generated CSV will follow this structure:
- image_path
- series_name
- episode
- timestamp
- detected_text 