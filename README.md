# DS YouTube Audio Downloader

Python tool to search YouTube for Vietnamese revolutionary songs, rank results, and download top candidates as MP3 using yt-dlp + FFmpeg.

## Requirements
- Python 3.12+
- FFmpeg installed and in PATH

Install dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

(Optional) one-shot setup:
```bash
source setup.sh
```

## Usage
Run with a specific song:
```bash
python download.py --name "Bài ca năm tấn" --limit 3 --quality 256 --skip-existing --verbose
```

Process whole `list.txt` concurrently:
```bash
python download.py --limit 2 --min-duration 120 --max-duration 600 --concurrency 3 --skip-existing --verbose
```

Use Android client (SABR fallback) or browser cookies:
```bash
python download.py --name "Tiến quân ca" --client android --cookies-from-browser chrome --verbose
```

Outputs are saved in `downloads/` by default. Failures are appended to `downloads/failures.log`.

## CLI Options
- `--name <str>`: Single song to process. Omit to read from `list.txt`.
- `--limit <int>`: Number of top candidates to download per song (default 5).
- `--quality <kbps>`: MP3 bitrate (default 192).
- `--output-dir <path>`: Output directory (default `downloads`).
- `--client {web|android}`: Force YouTube client (default web; android helpful for SABR).
- `--cookies-from-browser <name>`: Use cookies from a browser (`chrome`, `firefox`, ...).
- `--skip-existing`: Skip if target MP3 already exists.
- `--dry-run`: Show what would be downloaded without doing it.
- `--verbose`: Verbose logging.
- `--min-duration <sec>` / `--max-duration <sec>`: Filter by duration.
- `--concurrency <int>`: Parallelism for list mode (default 2).

## Notes
- Scoring prioritizes trusted artists, phrase match near start, reasonable title length, and view count; penalizes karaoke/cover/live and various non-target keywords.
- If you see format errors due to SABR, try `--client android` and/or add `--cookies-from-browser chrome`.

## License
MIT
