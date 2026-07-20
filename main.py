from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
import yt_dlp
import requests
import uvicorn
import os

app = FastAPI(title="Dexomder Video API")

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
    "instagram.com"
]

def is_youtube_url(url: str) -> bool:
    try:
        domain = urlparse(url).netloc.lower()
        return any(yt_domain in domain for yt_domain in YOUTUBE_DOMAINS)
    except Exception:
        return False

def get_working_proxy() -> str:
    proxy_source = "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all"
    
    try:
        response = requests.get(proxy_source, timeout=10)
        if response.status_code != 200:
            return None
        
        proxies = [p.strip() for p in response.text.splitlines() if p.strip()]
        
        for raw_proxy in proxies[:10]:
            proxy_url = f"http://{raw_proxy}"
            try:
                test_res = requests.get(
                    "https://www.google.com", 
                    proxies={"http": proxy_url, "https": proxy_url}, 
                    timeout=3
                )
                if test_res.status_code == 200:
                    return proxy_url
            except Exception:
                continue
    except Exception:
        pass
    
    return None

def format_size(bytes_size):
    if not bytes_size:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"

@app.get("/api/info")
def get_video_info(url: str):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True
    }
    
    if is_youtube_url(url):
        proxy = get_working_proxy()
        if proxy:
            ydl_opts['proxy'] = proxy
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
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
