import os
import pytest
import numpy as np
import cv2
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from main import ImageBattleGenerator

@pytest.fixture
def generator():
    return ImageBattleGenerator(similarity_threshold=0.4, output_dir='test_contents')

@pytest.fixture
def sample_frame():
    # Create a 100x100 frame with some text-like content
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.putText(frame, "Test", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return frame

def test_compare_frames(generator):
    # Create two similar frames
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Add slight difference
    frame2[0,0] = [255, 255, 255]
    
    similarity = generator.compare_frames(frame1, frame2)
    assert 0 <= similarity <= 1, "Similarity score should be between 0 and 1"
    assert similarity > 0.9, "Very similar frames should have high similarity score"

def test_has_subtitle_text(generator, sample_frame):
    has_text, text = generator.has_subtitle_text(sample_frame)
    assert isinstance(has_text, bool), "has_text should be boolean"
    assert isinstance(text, str), "text should be string"

def test_process_video(generator, tmp_path, mocker):
    # Mock video file and OpenCV functionality
    mock_video = tmp_path / "test_video.mp4"
    mock_video.write_text("")  # Create empty file
    
    # Mock cv2.VideoCapture
    mock_cap = mocker.MagicMock()
    mock_cap.get.return_value = 30  # fps
    mock_cap.read.side_effect = [(True, np.zeros((100, 100, 3))), (False, None)]
    mocker.patch('cv2.VideoCapture', return_value=mock_cap)
    
    # Mock OCR
    mocker.patch.object(generator.reader, 'readtext', return_value=[('', 'Test Text', 0.9)])
    
    # Process video
    frames_data = generator.process_video(str(mock_video), "test_series")
    
    assert isinstance(frames_data, list), "Should return list of frame data"
    assert len(frames_data) > 0, "Should process at least one frame"
    
    frame_data = frames_data[0]
    assert 'image_path' in frame_data
    assert 'series_name' in frame_data
    assert 'episode' in frame_data
    assert 'timestamp' in frame_data
    assert 'detected_text' in frame_data

def test_output_directory_creation(generator):
    test_dir = "test_output"
    if os.path.exists(test_dir):
        os.rmdir(test_dir)
    
    generator.output_dir = test_dir
    os.makedirs(os.path.join(test_dir, "test_series", "ep_01"), exist_ok=True)
    
    assert os.path.exists(test_dir), "Output directory should be created"
    assert os.path.exists(os.path.join(test_dir, "test_series")), "Series directory should be created"
    
    # Cleanup
    os.rmdir(os.path.join(test_dir, "test_series", "ep_01"))
    os.rmdir(os.path.join(test_dir, "test_series"))
    os.rmdir(test_dir) 