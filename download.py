import os
import re
import yt_dlp
import argparse
import requests
from typing import Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlencode

OUTPUT_DIR = "downloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# High-quality audio sources (better than YouTube)
HIGH_QUALITY_SOURCES = {
    # Prefer dedicated audio platforms first
    "soundcloud": {
        "name": "SoundCloud",
        "extractor": "soundcloud",
        "quality": "high",
        # yt-dlp supports SoundCloud search via scsearchN:QUERY
        "search_prefix": "scsearch20",
        "format": "bestaudio/best"
    },
    # YouTube with better audio formats as a fallback
    "high_quality": {
        "name": "YouTube Chất Lượng Cao",
        "extractor": "youtube",
        "quality": "high",
        "search_prefix": "ytsearch20",
        "format": "bestaudio[ext=m4a]/bestaudio/best"
    },
    "lossless": {
        "name": "YouTube Lossless",
        "extractor": "youtube", 
        "quality": "lossless",
        "search_prefix": "ytsearch20",
        "format": "bestaudio[ext=m4a]/bestaudio/best"
    },
    "premium": {
        "name": "YouTube Premium",
        "extractor": "youtube",
        "quality": "premium",
        "search_prefix": "ytsearch20",
        "format": "bestaudio[ext=m4a]/bestaudio/best"
    }
}

TRUSTED_ARTISTS = [
    # NSND/NSƯT (National Artists)
    "nsnd", "nsưt", "nghệ sĩ nhân dân", "nghệ sĩ ưu tú",
    
    # Classic revolutionary music artists
    "trọng tấn", "anh thơ", "thu hiền", "quang thọ", "đăng dương",
    "trung đức", "lan anh", "tân nhàn", "việt hoàn", "quang hưng",
    "minh thuận", "thanh hoa", "hồng nhung", "kim anh", "thu hà",
    "thanh hương", "minh phượng", "thu hiền", "kim thoa", "thu hiền",
    "minh thuận", "thanh hoa", "hồng nhung", "kim anh", "thu hà",
    
    # Renowned singers
    "quang lê", "đàm vĩnh hưng", "mỹ tâm", "hồng nhung", "thanh lam",
    "trần thu hà", "minh thuận", "thanh hoa", "kim anh", "thu hà",
    "minh phượng", "thu hiền", "kim thoa", "thu hiền", "minh thuận",
    
    # Official channels and quality indicators
    "official", "chính thức", "mv", "hq", "hd", "4k", "full hd",
    "nhạc cách mạng", "nhạc đỏ", "ca khúc cách mạng"
]

UNTRUSTED_KEYWORDS = [
    # Child/amateur performers
    "thần đồng", "thiếu nhi", "giọng ca nhí", "idol", "thần đồng âm nhạc",
    "ca sĩ nhí", "bé", "em bé", "trẻ em", "nhí", "kid", "child",
    
    # Low-quality content indicators
    "bolero", "cover", "karaoke", "remix", "beat", "instrumental",
    "nonstop", "dj", "acoustic", "mashup", "parody", "version",
    "nhạc nền", "backing track", "minus one", "playback",
    
    # Compilation/collection content
    "tuyển tập", "liên khúc", "lk", "medley", "album", "compilation",
    "full", "những bài hát", "top", "hay nhất", "best of", "greatest hits",
    "tổng hợp", "tuyển chọn", "bộ sưu tập", "collection",
    
    # Clickbait and promotional terms
    "siêu phẩm", "đặc biệt", "hot", "trending", "viral", "mới nhất",
    "2024", "2023", "2022", "2021", "2020", "năm nay", "tháng này",
    "không thể bỏ qua", "phải nghe", "nghe ngay", "xem ngay",
    "chưa từng có", "độc quyền", "exclusive", "premiere",
    
    # Low-quality video indicators
    "chất lượng thấp", "lq", "360p", "480p", "720p", "low quality",
    "tải về", "download", "free", "miễn phí", "không quảng cáo",
    
    # Spam and promotional content
    "sub", "subscribe", "like", "share", "comment", "đăng ký",
    "nhấn chuông", "bell", "notification", "thông báo",
    "link", "liên kết", "description", "mô tả", "info",
    
    # Unreliable sources
    "fanmade", "tự làm", "diy", "homemade", "amateur", "nghiệp dư",
    "không chính thức", "unofficial", "leak", "rò rỉ"
]

STRONG_PENALTIES = [
    # Obvious low-quality content
    "karaoke", "cover", "live", "concert", "show", "biểu diễn",
    "thần đồng", "ca sĩ nhí", "thiếu nhi", "giọng ca nhí",
    
    # Amateur/unprofessional content
    "fanmade", "tự làm", "diy", "homemade", "amateur", "nghiệp dư",
    "không chính thức", "unofficial", "leak", "rò rỉ",
    
    # Spam and promotional content
    "sub", "subscribe", "like", "share", "comment", "đăng ký",
    "nhấn chuông", "bell", "notification", "thông báo"
]

def clean_song_name(raw: str) -> str:
    """Xóa số thứ tự đầu dòng nếu có"""
    return re.sub(r"^\d+\.\s*", "", raw).strip()

def safe_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ trong tên file"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def search_high_quality_sources(song_name: str, source: str = "soundcloud") -> List[Dict[str, Any]]:
    """Tìm kiếm bài hát với format chất lượng cao"""
    try:
        if source not in HIGH_QUALITY_SOURCES:
            return []
        
        source_info = HIGH_QUALITY_SOURCES[source]
        query = f"{source_info['search_prefix']}:{song_name} nhạc cách mạng"
        
        # Sử dụng yt-dlp với format chất lượng cao
        search_opts = {
            "format": source_info['format'],
            "noplaylist": True,
            "quiet": True,
            "extract_flat": True,
            # extractor_args not needed for SoundCloud scsearch; keep simple
        }
        
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            try:
                info = ydl.extract_info(query, download=False)
                entries = info.get("entries", [])
                if entries:
                    # Lọc và sắp xếp theo chất lượng
                    filtered_entries = []
                    for entry in entries[:15]:  # Lấy nhiều hơn để lọc
                        duration = entry.get("duration", 0)
                        if duration > 30:  # Ít nhất 30 giây
                            # Ưu tiên các video có chất lượng cao
                            title = entry.get("title", "").lower()
                            quality_score = 0
                            
                            # Bonus cho các từ khóa chất lượng cao
                            if any(word in title for word in ["official", "mv", "hq", "hd", "4k", "chính thức"]):
                                quality_score += 5
                            if any(word in title for word in ["lossless", "flac", "wav", "hi-res"]):
                                quality_score += 10
                            if any(word in title for word in ["karaoke", "cover", "remix", "beat"]):
                                quality_score -= 5
                                
                            entry["quality_score"] = quality_score
                            filtered_entries.append(entry)
                    
                    # Sắp xếp theo quality_score
                    filtered_entries.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
                    return filtered_entries[:10]  # Trả về top 10
            except Exception as e:
                print(f"⚠️ {source_info['name']} không có kết quả: {e}")
                return []
        return []
    except Exception as e:
        print(f"⚠️ Lỗi khi tìm kiếm trên {source_info['name']}: {e}")
        return []

def download_from_high_quality_source(song_name: str, entry: Dict[str, Any], output_dir: str, quality: int, source: str = "soundcloud") -> bool:
    """Tải file MP3 với chất lượng cao"""
    try:
        if source not in HIGH_QUALITY_SOURCES:
            return False
            
        source_info = HIGH_QUALITY_SOURCES[source]
        # Prefer direct URL if provided by extractor (SoundCloud provides page URL)
        url = entry.get('url') or (f"https://www.youtube.com/watch?v={entry['id']}" if 'id' in entry else '')
        
        if not url:
            return False
            
        # Tạo tên file
        title = entry.get("title", "Unknown")
        quality_score = entry.get("quality_score", 0)
        filename_prefix = f"{safe_filename(song_name)} - {source_info['name']} - {safe_filename(title)}.%(ext)s"
        output_path = os.path.join(output_dir, filename_prefix.replace(".%(ext)s", ".mp3"))
        
        # Cấu hình yt-dlp cho chất lượng cao
        download_opts = {
            "format": source_info['format'],
            "outtmpl": os.path.join(output_dir, filename_prefix),
            "noplaylist": True,
            "quiet": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(quality),
            }],
            # Keep defaults; yt-dlp will pick bestaudio and convert to mp3
        }
        
        with yt_dlp.YoutubeDL(download_opts) as ydl:
            ydl.download([url])
            return True
            
    except Exception as e:
        print(f"⚠️ Lỗi khi tải từ {source_info['name']}: {e}")
        return False

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
    
    # Strong penalties for obvious clickbait/cover content
    for bad in STRONG_PENALTIES:
        if bad in title:
            score -= 20  # Increased penalty
    
    # General untrusted keywords
    untrusted_count = sum(1 for bad in UNTRUSTED_KEYWORDS if bad in title)
    if untrusted_count > 0:
        score -= 10 + (untrusted_count * 3)  # Penalty increases with more keywords
    
    # Trusted artists bonus
    if any(artist in title for artist in TRUSTED_ARTISTS):
        score += 8
    
    # Song name matching (most important factor)
    if song_lower in title:
        score += 8  # Increased base bonus
        # Bonus if phrase appears near the start
        idx = title.find(song_lower)
        if idx == 0:
            score += 8  # Increased bonus for exact start
        elif idx <= 15:
            score += 4  # Increased bonus for early appearance
    
    # Word matching bonus
    matching_words = sum(1 for w in song_words if w in title)
    score += matching_words * 1.5  # Slightly increased per word
    
    # Title length penalties (stronger penalties for clickbait)
    title_length = len(title)
    if title_length < 50:
        score += 3  # Bonus for concise titles
    elif title_length < 80:
        score += 1  # Small bonus for reasonable length
    elif title_length > 120:
        score -= 8  # Strong penalty for very long titles (likely clickbait)
    elif title_length > 100:
        score -= 4  # Medium penalty for long titles
    
    # View count with much reduced weight and logarithmic scaling
    view_count = entry.get("view_count") or 0
    try:
        view_num = float(view_count)
        if view_num > 0:
            # Use logarithmic scaling to reduce impact of high view counts
            import math
            score += math.log10(view_num + 1) * 0.5  # Much smaller multiplier
    except Exception:
        pass
    
    # Additional penalty for titles with excessive promotional keywords
    promotional_keywords = ["top", "hay nhất", "đặc biệt", "siêu phẩm", "tuyển tập", "liên khúc"]
    promo_count = sum(1 for kw in promotional_keywords if kw in title)
    if promo_count > 2:  # More than 2 promotional keywords
        score -= promo_count * 2
    
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

def download_song(song_name, limit: int, output_dir: str, quality: int, verbose: bool, client: str, cookies_from_browser: str | None, skip_existing: bool, dry_run: bool, min_duration: int | None, max_duration: int | None, use_mp3_sites: bool = False, mp3_site: str = "high_quality") -> Tuple[int, int, List[str]]:
    successes = 0
    failures: List[str] = []
    
    # Thử tải từ nguồn chất lượng cao trước (nếu được bật)
    if use_mp3_sites:
        print(f"🎵 Tìm kiếm '{song_name}' trên {HIGH_QUALITY_SOURCES[mp3_site]['name']}...")
        hq_results = search_high_quality_sources(song_name, mp3_site)
        
        if hq_results:
            print(f"✅ Tìm thấy {len(hq_results)} kết quả từ {HIGH_QUALITY_SOURCES[mp3_site]['name']}")
            for idx, result in enumerate(hq_results[:limit], 1):
                title = result.get("title", "Unknown")
                duration = result.get("duration", 0)
                
                filename_prefix = f"{safe_filename(song_name)} - {HIGH_QUALITY_SOURCES[mp3_site]['name']}{idx} - {safe_filename(title)}.mp3"
                output_path = os.path.join(output_dir, filename_prefix)
                
                if skip_existing and os.path.exists(output_path):
                    if verbose:
                        print(f"⏭️ Bỏ qua (đã tồn tại): {output_path}")
                    continue
                
                if dry_run:
                    print(f"🧪 DRY-RUN sẽ lưu: {output_path}")
                    print(f"   📊 {title} ({duration}s) - Chất lượng cao")
                    successes += 1
                    continue
                
                try:
                    if download_from_high_quality_source(song_name, result, output_dir, quality, mp3_site):
                        print(f"✅ Đã tải: {title} ({duration}s) - Chất lượng cao")
                        successes += 1
                    else:
                        failures.append(f"{song_name}\t{HIGH_QUALITY_SOURCES[mp3_site]['name']}{idx}\t{title}\tTải thất bại")
                except Exception as e:
                    failures.append(f"{song_name}\t{HIGH_QUALITY_SOURCES[mp3_site]['name']}{idx}\t{title}\t{e}")
            
            if successes > 0:
                return (successes, len(failures), failures)
        else:
            print(f"⚠️ Không tìm thấy kết quả trên {HIGH_QUALITY_SOURCES[mp3_site]['name']}, chuyển sang YouTube...")
    
    # Fallback về YouTube nếu MP3 sites không có kết quả
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
    parser.add_argument("--use-mp3-sites", action="store_true", help="Thử tải từ nguồn chất lượng cao trước (SoundCloud, Bandcamp, Vimeo)")
    parser.add_argument("--mp3-site", choices=list(HIGH_QUALITY_SOURCES.keys()), default="high_quality", help="Chọn nguồn chất lượng cao (mặc định high_quality)")
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
            use_mp3_sites=args.use_mp3_sites,
            mp3_site=args.mp3_site,
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
                    args.use_mp3_sites,
                    args.mp3_site,
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
