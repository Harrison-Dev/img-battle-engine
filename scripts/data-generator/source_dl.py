import os
import sys
import subprocess
from urllib.parse import urlparse, parse_qs

def get_you_get_path():
    """Get the you-get executable path based on the platform."""
    venv_dir = os.path.dirname(os.path.dirname(sys.executable))
    if sys.platform == 'win32':
        return os.path.join(venv_dir, 'Scripts', 'you-get.exe')
    return os.path.join(venv_dir, 'bin', 'you-get')

YOU_GET_PATH = get_you_get_path()

def ensure_downloads_dir():
    """Ensure downloads directory exists and return its path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    downloads_dir = os.path.join(script_dir, 'downloads')
    if not os.path.exists(downloads_dir):
        os.makedirs(downloads_dir)
    return downloads_dir

def run_subprocess(cmd, **kwargs):
    """Run a subprocess command with proper encoding handling."""
    try:
        # Force UTF-8 encoding for both stdout and stderr
        kwargs.update({
            'encoding': 'utf-8',
            'errors': 'replace',
            'env': {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
        })
        return subprocess.run(cmd, **kwargs)
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        if e.stdout:
            print("stdout:", e.stdout)
        if e.stderr:
            print("stderr:", e.stderr)
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        raise

def download_video(video_url):
    """Download a single video."""
    downloads_dir = ensure_downloads_dir()
    original_dir = os.getcwd()
    
    try:
        # Change to downloads directory
        os.chdir(downloads_dir)
        
        # First, check available formats
        print("Checking available formats...")
        result = run_subprocess(
            [YOU_GET_PATH, '-i', video_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Failed to get video info: {result.stderr}")
        print(result.stdout)
        
        # Download video
        print("\nStarting download...")
        result = run_subprocess(
            [YOU_GET_PATH, video_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Failed to download video: {result.stderr}")
        print(result.stdout)
        
        print("Download completed!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise
    
    finally:
        # Always return to original directory
        os.chdir(original_dir)

def download_playlist(playlist_url):
    """Download all videos in a playlist."""
    downloads_dir = ensure_downloads_dir()
    original_dir = os.getcwd()
    
    try:
        # Change to downloads directory
        os.chdir(downloads_dir)
        
        # First, check available formats
        print("Checking available formats...")
        result = run_subprocess(
            [YOU_GET_PATH, '-i', playlist_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Failed to get playlist info: {result.stderr}")
        print(result.stdout)
        
        # Download playlist videos
        print("\nStarting downloads...")
        result = run_subprocess(
            [YOU_GET_PATH, '--playlist', playlist_url],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise Exception(f"Failed to download playlist: {result.stderr}")
        print(result.stdout)
        
        print("Download completed!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        raise
    
    finally:
        # Always return to original directory
        os.chdir(original_dir)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python source_dl.py <video_or_playlist_url>")
        sys.exit(1)
    
    if not os.path.exists(YOU_GET_PATH):
        print(f"Error: you-get not found at {YOU_GET_PATH}")
        print("Please ensure you-get is installed in your virtual environment.")
        sys.exit(1)
        
    url = sys.argv[1]
    if 'playlist' in url or 'list=' in url:
        download_playlist(url)
    else:
        download_video(url) 