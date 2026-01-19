#!/usr/bin/env python3
"""
Download audio from YouTube URLs using yt-dlp.
Outputs a WAV file suitable for audio analysis.
"""

import sys
import json
import os
import tempfile
import re


class NullLogger:
    """Suppress all yt-dlp logging output."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def is_valid_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube URL."""
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/embed/[\w-]+',
        r'(https?://)?(www\.)?youtube\.com/v/[\w-]+',
        r'(https?://)?music\.youtube\.com/watch\?v=[\w-]+',
    ]
    return any(re.match(pattern, url) for pattern in youtube_patterns)


def download_youtube_audio(url: str, output_dir: str = None) -> dict:
    """
    Download audio from a YouTube URL.

    Args:
        url: YouTube video URL
        output_dir: Directory to save the audio file (default: temp dir)

    Returns:
        dict with success status, audio path, and video title
    """
    try:
        import yt_dlp
    except ImportError:
        return {
            'success': False,
            'error': 'yt-dlp not installed. Run: pip install yt-dlp'
        }

    if not is_valid_youtube_url(url):
        return {
            'success': False,
            'error': 'Invalid YouTube URL'
        }

    if output_dir is None:
        output_dir = tempfile.gettempdir()

    # Generate output filename
    output_template = os.path.join(output_dir, 'harmony_yt_%(id)s.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'extract_flat': False,
        'logger': NullLogger(),
        # Options to help avoid 403 errors
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        'socket_timeout': 30,
        'retries': 3,
    }

    last_error = None

    # Try different browser cookies to help with 403 errors
    for browser in ['chrome', 'firefox', 'safari', None]:
        try:
            opts = ydl_opts.copy()
            if browser:
                opts['cookiesfrombrowser'] = (browser,)
            else:
                # Remove cookies option if set from previous iteration
                opts.pop('cookiesfrombrowser', None)

            with yt_dlp.YoutubeDL(opts) as ydl:
                # Extract info first to get the title and ID
                info = ydl.extract_info(url, download=False)
                video_id = info.get('id', 'unknown')
                video_title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)

                # Now download
                ydl.download([url])

                # Construct the output path
                output_path = os.path.join(output_dir, f'harmony_yt_{video_id}.mp3')

                if not os.path.isfile(output_path):
                    # Try finding the file with different extension patterns
                    for ext in ['mp3', 'wav', 'webm', 'm4a']:
                        alt_path = os.path.join(output_dir, f'harmony_yt_{video_id}.{ext}')
                        if os.path.isfile(alt_path):
                            output_path = alt_path
                            break

                if not os.path.isfile(output_path):
                    last_error = 'Download completed but output file not found'
                    continue

                return {
                    'success': True,
                    'audioPath': output_path,
                    'title': video_title,
                    'duration': duration
                }

        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            if 'Video unavailable' in error_msg:
                return {'success': False, 'error': 'Video is unavailable or private'}
            elif 'age' in error_msg.lower():
                return {'success': False, 'error': 'Video is age-restricted'}
            else:
                last_error = error_msg
                continue  # Try next browser
        except Exception as e:
            last_error = str(e)
            continue  # Try next browser

    # All attempts failed
    return {
        'success': False,
        'error': f'Download failed: {last_error}'
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            'success': False,
            'error': 'Usage: download_youtube.py <youtube_url> [output_dir]'
        }))
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None

    result = download_youtube_audio(url, output_dir)
    print(json.dumps(result))

    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
