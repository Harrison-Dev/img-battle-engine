import os
import sys
import subprocess
from urllib.parse import urlparse, parse_qs

# Get the you-get executable path
PYTHON_SCRIPTS = os.path.join(os.path.dirname(sys.executable), 'Scripts')
YOU_GET_PATH = os.path.join(PYTHON_SCRIPTS, 'you-get.exe')

def download_playlist(playlist_url):
    # Create downloads directory if it doesn't exist
    if not os.path.exists('downloads'):
        os.makedirs('downloads')
    
    # Change to downloads directory
    os.chdir('downloads')
    
    try:
        # First, check available formats
        print("Checking available formats...")
        subprocess.run([YOU_GET_PATH, '-i', playlist_url])
        
        # Download playlist videos
        print("\nStarting downloads...")
        subprocess.run([YOU_GET_PATH,
                       '--playlist',  # Add playlist flag
                       playlist_url])
        
        print("Download completed!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python yt_playlist_downloader.py <playlist_url>")
        sys.exit(1)
    
    if not os.path.exists(YOU_GET_PATH):
        print(f"Error: you-get not found at {YOU_GET_PATH}")
        sys.exit(1)
        
    playlist_url = sys.argv[1]
    download_playlist(playlist_url) 