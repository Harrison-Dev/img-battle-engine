#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

YT_DLP_PATH = "yt-dlp"  # 確保已安裝並在 PATH 裡

def ensure_downloads_dir():
    """確保 downloads 目錄存在，並回傳其絕對路徑。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    downloads = os.path.join(script_dir, 'downloads')
    os.makedirs(downloads, exist_ok=True)
    return downloads

def run_subprocess(cmd, **kwargs):
    """執行 subprocess，強制 UTF-8 編碼輸出。"""
    kwargs.update({
        'encoding': 'utf-8',
        'errors': 'replace',
        'env': {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    })
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"命令失敗：{' '.join(cmd)}\n{result.stderr}")
    return result

def download_video(url):
    downloads = ensure_downloads_dir()
    print(f"→ 下載到：{downloads}")
    # 列出可用格式
    info = run_subprocess([YT_DLP_PATH, '-F', url, '--no-playlist'], capture_output=True)
    print(info.stdout)
    # 只抓最佳 MP4 影片（無音軌）
    dl = run_subprocess([
        YT_DLP_PATH,
        '--no-playlist',
        '-f', 'bestvideo[ext=mp4]',
        '-o', os.path.join(downloads, '%(title)s.%(ext)s'),
        url
    ], capture_output=True)
    print(dl.stdout)
    print("影片下載完成！")

def download_playlist(url):
    downloads = ensure_downloads_dir()
    print(f"→ 下載到：{downloads}")
    # 列出可用格式
    info = run_subprocess([YT_DLP_PATH, '-F', url, '--yes-playlist'], capture_output=True)
    print(info.stdout)
    # 只抓最佳 MP4 影片（無音軌）
    dl = run_subprocess([
        YT_DLP_PATH,
        '--yes-playlist',
        '-f', 'bestvideo[ext=mp4]',
        '-o', os.path.join(downloads, '%(playlist_index)03d-%(title)s.%(ext)s'),
        url
    ], capture_output=True)
    print(dl.stdout)
    print("清單下載完成！")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python source_dl.py <video_or_playlist_url>")
        sys.exit(1)
    if shutil.which(YT_DLP_PATH) is None:
        print(f"Error: `{YT_DLP_PATH}` not found. Please install yt-dlp.")
        sys.exit(1)

    target = sys.argv[1]
    if 'playlist' in target or 'list=' in target:
        download_playlist(target)
    else:
        download_video(target)
