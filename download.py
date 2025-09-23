import os
import re
import yt_dlp
import argparse
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TRUSTED_ARTISTS = [
    "trọng tấn", "anh thơ", "thu hiền", "quang thọ", "đăng dương",
    "trung đức", "lan anh", "tân nhàn", "việt hoàn", "nsnd", "nsưt"
]

UNTRUSTED_KEYWORDS = [
    "thần đồng", "bolero", "thiếu nhi", "giọng ca nhí", "idol",
    "cover", "karaoke", "remix", "beat", "instrumental",
    "nonstop", "dj", "acoustic", "mashup", "parody",
    "tuyển tập", "liên khúc", "lk", "medley", "album",
    "full", "những bài hát", "top", "hay nhất"
]

STRONG_PENALTIES = ["karaoke", "cover", "live"]

def clean_song_name(raw: str) -> str:
    """Xóa số thứ tự đầu dòng nếu có"""
    return re.sub(r"^\d+\.\s*", "", raw).strip()

def safe_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def score_entry(entry, song_name, min_duration: int | None, max_duration: int | None):
    title = entry.get("title", "").lower()
    if not title:
        return -999

    # Duration filtering (if available)
    duration = entry.get("duration")
    if isinstance(duration, (int, float)):
        if (min_duration and duration < min_duration) or (max_duration and duration > max_duration):
            return -999

    song_lower = song_name.lower()
    song_words = [w for w in song_lower.split() if len(w) > 2]

    score = 0.0
    # Strong penalties
    for bad in STRONG_PENALTIES:
        if bad in title:
            score -= 15
    # General untrusted
    if any(bad in title for bad in UNTRUSTED_KEYWORDS):
        score -= 10
    if any(artist in title for artist in TRUSTED_ARTISTS):
        score += 8
    if song_lower in title:
        score += 5
        # Bonus if phrase appears near the start
        idx = title.find(song_lower)
        if idx == 0:
            score += 6
        elif idx <= 15:
            score += 3
    score += sum(1 for w in song_words if w in title)
    if len(title) < 60:
        score += 2
    if len(title) > 90:
        score -= 2
    view_count = entry.get("view_count") or 0
    try:
        score += float(view_count) / 500_000.0
    except Exception:
        pass
    return score

def build_search_opts(verbose: bool, client: str, cookies_from_browser: str | None) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": not verbose,
        "extract_flat": True,
    }
    extractor_args = {}
    if client == "android":
        extractor_args = {"youtube": {"player_client": ["android"]}}
    if extractor_args:
        opts["extractor_args"] = extractor_args
    if cookies_from_browser:
        # Accept a browser name like 'chrome', 'firefox'
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    return opts

def build_download_opts(output_dir: str, filename_prefix: str, quality: int, verbose: bool, client: str, cookies_from_browser: str | None) -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(output_dir, filename_prefix),
        "noplaylist": True,
        "quiet": not verbose,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": str(quality),
        }],
    }
    extractor_args = {}
    if client == "android":
        extractor_args = {"youtube": {"player_client": ["android"]}}
    if extractor_args:
        opts["extractor_args"] = extractor_args
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    return opts

def try_download(url: str, base_opts: Dict[str, Any], fallback_android: bool, verbose: bool) -> None:
    # First attempt
    try:
        with yt_dlp.YoutubeDL(base_opts) as ydl_download:
            ydl_download.download([url])
        return
    except Exception as e:
        if verbose:
            print(f"⚠️ Lỗi lần 1: {e}")
        if not fallback_android:
            raise
    # Fallback with android client if requested
    try:
        fallback_opts = dict(base_opts)
        extractor_args = {"youtube": {"player_client": ["android"]}}
        if "extractor_args" in fallback_opts:
            # Merge
            existing = fallback_opts["extractor_args"]
            if isinstance(existing, dict) and "youtube" in existing:
                existing["youtube"]["player_client"] = ["android"]
                extractor_args = existing
        fallback_opts["extractor_args"] = extractor_args
        with yt_dlp.YoutubeDL(fallback_opts) as ydl_download:
            ydl_download.download([url])
    except Exception as e2:
        raise RuntimeError(f"Tải thất bại sau khi thử fallback android: {e2}")

def download_song(song_name, limit: int, output_dir: str, quality: int, verbose: bool, client: str, cookies_from_browser: str | None, skip_existing: bool, dry_run: bool, min_duration: int | None, max_duration: int | None) -> Tuple[int, int, List[str]]:
    successes = 0
    failures: List[str] = []
    query = f"ytsearch20:{song_name} nhạc cách mạng"

    search_opts = build_search_opts(verbose=verbose, client=client, cookies_from_browser=cookies_from_browser)
    with yt_dlp.YoutubeDL(search_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", [])
            if not entries:
                print(f"⚠️ Không tìm thấy kết quả cho: {song_name}")
                return (0, 1, [f"{song_name}\tKhông tìm thấy kết quả"])

            scored = [(score_entry(e, song_name, min_duration, max_duration), e) for e in entries]
            scored = [s for s in scored if s[0] > -999]
            scored.sort(key=lambda x: x[0], reverse=True)
            topn = scored[:max(1, limit)]

            if not topn:
                print(f"⚠️ Không có ứng viên hợp lệ cho: {song_name}")
                return (0, 1, [f"{song_name}\tKhông có ứng viên hợp lệ"])

            for idx, (score, e) in enumerate(topn, start=1):
                url = f"https://www.youtube.com/watch?v={e['id']}"
                title = e.get("title", "Unknown")
                print(f"🎵 {song_name} [Top {idx}] {title} ({url}) | Score={score:.1f}")

                filename_prefix = f"{safe_filename(song_name)} - Top{idx} - {safe_filename(title)}.%(ext)s"
                expected_mp3 = os.path.join(output_dir, filename_prefix.replace(".%(ext)s", ".mp3"))

                if skip_existing and os.path.exists(expected_mp3):
                    if verbose:
                        print(f"⏭️ Bỏ qua (đã tồn tại): {expected_mp3}")
                    continue

                if dry_run:
                    print(f"🧪 DRY-RUN sẽ lưu: {expected_mp3}")
                    continue

                ydl_opts_download = build_download_opts(
                    output_dir=output_dir,
                    filename_prefix=filename_prefix,
                    quality=quality,
                    verbose=verbose,
                    client=client,
                    cookies_from_browser=cookies_from_browser,
                )
                try:
                    try_download(url, ydl_opts_download, fallback_android=(client != "android"), verbose=verbose)
                    successes += 1
                except Exception as e:
                    msg = f"{song_name}\tTop{idx}\t{title}\t{e}"
                    print(f"❌ {msg}")
                    failures.append(msg)

        except Exception as e:
            msg = f"{song_name}\t{e}"
            print(f"❌ Lỗi khi xử lý {song_name}: {e}")
            failures.append(msg)
    return (successes, len(failures), failures)

def main():
    parser = argparse.ArgumentParser(description="Tải nhạc cách mạng từ YouTube")
    parser.add_argument("--name", type=str, help="Tên bài hát để tải TopN (nếu không có sẽ tải toàn bộ list.txt)")
    parser.add_argument("--limit", type=int, default=5, help="Số ứng viên TopN để tải (mặc định 5)")
    parser.add_argument("--quality", type=int, default=192, help="Chất lượng mp3 kbps (mặc định 192)")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR, help="Thư mục lưu (mặc định downloads)")
    parser.add_argument("--client", choices=["web", "android"], default="web", help="Client YouTube (fallback SABR: android)")
    parser.add_argument("--cookies-from-browser", type=str, default=None, help="Tên trình duyệt để lấy cookies (vd: chrome, firefox)")
    parser.add_argument("--skip-existing", action="store_true", help="Bỏ qua nếu file mp3 đã tồn tại")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ hiển thị dự định tải, không tải")
    parser.add_argument("--verbose", action="store_true", help="Hiển thị log chi tiết")
    parser.add_argument("--min-duration", type=int, default=None, help="Lọc tối thiểu thời lượng (giây)")
    parser.add_argument("--max-duration", type=int, default=None, help="Lọc tối đa thời lượng (giây)")
    parser.add_argument("--concurrency", type=int, default=2, help="Số bài xử lý song song trong chế độ list (mặc định 2)")
    args = parser.parse_args()

    out_dir = args.output_dir or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    if args.name:
        download_song(
            clean_song_name(args.name),
            limit=args.limit,
            output_dir=out_dir,
            quality=args.quality,
            verbose=args.verbose,
            client=args.client,
            cookies_from_browser=args.cookies_from_browser,
            skip_existing=args.skip_existing,
            dry_run=args.dry_run,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
        )
    else:
        with open("list.txt", "r", encoding="utf-8") as f:
            songs = [clean_song_name(line) for line in f if line.strip()]
        total_success = 0
        total_failed = 0
        all_failures: List[str] = []
        # Concurrent processing of songs (each song may download up to N items)
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
            futures = {
                executor.submit(
                    download_song,
                    song,
                    args.limit,
                    out_dir,
                    args.quality,
                    args.verbose,
                    args.client,
                    args.cookies_from_browser,
                    args.skip_existing,
                    args.dry_run,
                    args.min_duration,
                    args.max_duration,
                ): song for song in songs
            }
            for future in as_completed(futures):
                try:
                    s, f, flist = future.result()
                    total_success += s
                    total_failed += f
                    if flist:
                        all_failures.extend(flist)
                except Exception as e:
                    total_failed += 1
                    all_failures.append(f"{futures[future]}\t{e}")
        # Summary
        print(f"\n📊 Tóm tắt: thành công={total_success}, thất bại={total_failed}")
        if all_failures:
            log_path = os.path.join(out_dir, "failures.log")
            try:
                with open(log_path, "a", encoding="utf-8") as lf:
                    for line in all_failures:
                        lf.write(line + "\n")
                print(f"📝 Ghi thất bại vào: {log_path}")
            except Exception as e:
                print(f"⚠️ Không thể ghi failures.log: {e}")

if __name__ == "__main__":
    main()
