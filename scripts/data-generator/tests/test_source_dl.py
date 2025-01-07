import pytest
import os
import sys
from pathlib import Path

# Add parent directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from source_dl import download_video, download_playlist

@pytest.fixture
def setup_downloads_dir():
    """Setup and cleanup downloads directory"""
    downloads_dir = 'downloads'
    # Create directory if it doesn't exist
    os.makedirs(downloads_dir, exist_ok=True)
    
    yield
    
    # Cleanup after tests
    if os.path.exists(downloads_dir):
        for file in os.listdir(downloads_dir):
            try:
                os.remove(os.path.join(downloads_dir, file))
            except:
                pass
        try:
            os.rmdir(downloads_dir)
        except:
            pass

def test_download_video(setup_downloads_dir, mocker):
    """Test single video download"""
    # Mock subprocess.run
    mock_run = mocker.patch('subprocess.run')
    
    test_url = "https://youtube.com/watch?v=test123"
    download_video(test_url)
    
    # Check that subprocess.run was called twice (once for -i, once for download)
    assert mock_run.call_count == 2
    
    # Verify the calls
    calls = mock_run.call_args_list
    assert '-i' in str(calls[0])  # First call should check formats
    assert test_url in str(calls[1])  # Second call should download

def test_download_playlist(setup_downloads_dir, mocker):
    """Test playlist download"""
    # Mock subprocess.run
    mock_run = mocker.patch('subprocess.run')
    
    test_url = "https://youtube.com/playlist?list=test123"
    download_playlist(test_url)
    
    # Check that subprocess.run was called twice
    assert mock_run.call_count == 2
    
    # Verify the calls
    calls = mock_run.call_args_list
    assert '-i' in str(calls[0])  # First call should check formats
    assert '--playlist' in str(calls[1])  # Second call should have playlist flag
    assert test_url in str(calls[1])

def test_downloads_directory_creation(setup_downloads_dir, mocker):
    """Test that downloads directory is created if it doesn't exist"""
    # Mock subprocess.run to prevent actual downloads
    mocker.patch('subprocess.run')
    
    # Remove downloads directory if it exists
    downloads_dir = 'downloads'
    if os.path.exists(downloads_dir):
        try:
            os.rmdir(downloads_dir)
        except:
            pass
    
    download_video("https://youtube.com/watch?v=test123")
    assert os.path.exists(downloads_dir), "Downloads directory should be created"

def test_error_handling(setup_downloads_dir, mocker):
    """Test error handling during download"""
    # Mock subprocess.run to raise an exception
    mocker.patch('subprocess.run', side_effect=Exception("Download failed"))
    
    try:
        download_video("https://youtube.com/watch?v=test123")
        pytest.fail("Should have raised an exception")
    except Exception as e:
        assert "Download failed" in str(e) 