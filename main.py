from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import uvicorn
import os

app = FastAPI(title="Dexomder Video API")

# Allow requests from any frontend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats_data = {
                "video_audio": [],
                "video_only": [],
                "audio_only": []
            }
            
            # Sort formats from best to worst quality loosely based on height/bitrate
            raw_formats = info.get('formats', [])
            raw_formats.reverse() 
            
            for f in raw_formats:
                # Skip formats that do not provide a direct downloadable URL or are manifests
                if not f.get('url') or f.get('protocol') in ['m3u8', 'm3u8_native']:
                    continue
                
                has_video = f.get('vcodec') != 'none'
                has_audio = f.get('acodec') != 'none'
                
                # Determine resolution/quality string
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
    # Render assigns a dynamic port via the PORT environment variable
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
