from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
import yt_dlp
import requests
import uvicorn
import os
import asyncio
import concurrent.futures

app = FastAPI(title="Dexomder Video API")

# Allow requests from any frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

YOUTUBE_DOMAINS = [
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "snapchat.com", 
    "instagram.com", 
    "ig.me", "mojapp.in", 
    "tiktok.com",
    "vm.tiktok.com", 
    "vt.tiktok.com", 
    "x.com", 
    "twitter.com",
    "t.co", "facebook.com", 
    "fb.com",
    "fb.watch", 
    "fb.me", 
    "m.facebook.com"
]

def is_youtube_url(url: str) -> bool:
    """Checks if the input URL belongs to YouTube."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(yt_domain in domain for yt_domain in YOUTUBE_DOMAINS)
    except Exception:
        return False

def test_single_proxy(raw_proxy: str) -> str:
    """Tests a single proxy against a Google endpoint to verify connectivity."""
    proxy_url = f"http://{raw_proxy}"
    try:
        res = requests.get(
            "https://www.google.com",
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=3
        )
        if res.status_code == 200:
            return proxy_url
    except Exception:
        pass
    return None

def get_working_proxies(target_count: int = 2, max_check: int = 100) -> list[str]:
    """
    Tests up to max_check (100) proxies in parallel using ThreadPoolExecutor.
    Stops immediately as soon as target_count (2) working proxies are found.
    """
    proxy_source = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
    try:
        response = requests.get(proxy_source, timeout=10)
        if response.status_code != 200:
            return []
        proxies = [p.strip() for p in response.text.splitlines() if p.strip()][:max_check]
    except Exception:
        return []

    working_proxies = []
    
    # Check up to 20 proxies concurrently in worker threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {executor.submit(test_single_proxy, p): p for p in proxies}
        for future in concurrent.futures.as_completed(future_to_proxy):
            res = future.result()
            if res:
                working_proxies.append(res)
                # Stop checking as soon as the target count of working proxies is found
                if len(working_proxies) >= target_count:
                    break

    return working_proxies

def extract_info_sync(url: str, proxy: str = None):
    """Synchronous yt-dlp extraction wrapper."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'force_ipv6': True
    }
    if proxy:
        ydl_opts['proxy'] = proxy

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

async def fetch_ytdlp_racing(url: str, proxies: list[str]):
    """
    Launches concurrent extraction requests using different proxy IPs.
    Returns as soon as the fastest request succeeds and cancels the remaining one.
    """
    loop = asyncio.get_running_loop()

    if not proxies:
        # Fallback to direct request if no proxies were found
        return await loop.run_in_executor(None, extract_info_sync, url, None)

    # loop.run_in_executor already returns an awaitable Future,
    # so we do NOT need asyncio.create_task() around it.
    tasks = [
        loop.run_in_executor(None, extract_info_sync, url, proxy)
        for proxy in proxies
    ]

    pending = set(tasks)
    last_exception = None

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for completed_task in done:
            try:
                result = completed_task.result()
                # Cancel all remaining pending tasks as soon as 1 request succeeds
                for remaining_task in pending:
                    remaining_task.cancel()
                return result
            except Exception as e:
                last_exception = e

    if last_exception:
        raise last_exception
    raise HTTPException(status_code=400, detail="Failed to fetch video details from proxies.")

def format_size(bytes_size):
    if not bytes_size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

@app.get("/api/info")
async def get_video_info(url: str):
    try:
        proxies = []
        if is_youtube_url(url):
            # 1. Concurrently test up to 100 proxies and stop when 2 working proxies are found
            loop = asyncio.get_running_loop()
            proxies = await loop.run_in_executor(None, get_working_proxies, 2, 100)

        # 2. Pass link to yt-dlp in a batch of 2 parallel requests with different IPs
        # 3. As soon as 1 succeeds, stop/cancel the 2nd request immediately
        info = await fetch_ytdlp_racing(url, proxies)

        formats_data = {
            "video_audio": [],
            "video_only": [],
            "audio_only": []
        }

        raw_formats = info.get('formats', [])
        raw_formats.reverse()

        for f in raw_formats:
            if not f.get('url') or f.get('protocol') in ['m3u8', 'm3u8_native']:
                continue

            has_video = f.get('vcodec') != 'none'
            has_audio = f.get('acodec') != 'none'

            if has_video:
                resolution = f.get('format_note') or f"{f.get('height', '?')}p"
            else:
                resolution = f.get('format_note') or f"{int(f.get('abr', 0))} kbps" if f.get('abr') else "Audio"

            ext = f.get('ext', 'unknown')
            size = format_size(f.get('filesize') or f.get('filesize_approx'))

            fmt_obj = {
                "format_id": f.get('format_id'),
                "ext": ext,
                "resolution": resolution,
                "size": size,
                "url": f.get('url')
            }

            if has_video and has_audio:
                formats_data["video_audio"].append(fmt_obj)
            elif has_video and not has_audio:
                formats_data["video_only"].append(fmt_obj)
            elif not has_video and has_audio:
                formats_data["audio_only"].append(fmt_obj)

        return {
            "success": True,
            "title": info.get('title', 'Unknown Title'),
            "thumbnail": info.get('thumbnail', ''),
            "duration": info.get('duration_string') or info.get('duration', 0),
            "uploader": info.get('uploader', 'Unknown'),
            "formats": formats_data
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
