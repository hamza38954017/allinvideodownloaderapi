# Dexomder Video API

A fast, lightweight Python REST API powered by **FastAPI** and **yt-dlp**. This web service extracts video and audio download links from supported platforms (YouTube, Twitter, TikTok, etc.) and categorizes them by format and quality. 

This repository contains the backend API code designed to be deployed on Render's free tier, while the frontend (PHP) is hosted separately.

©️ copyright by Gemini

---

## 🚀 Features

*   **Universal Support:** Powered by `yt-dlp`, supporting hundreds of video hosting platforms.
*   **Smart Categorization:** Automatically sorts download links into three distinct categories:
    *   Video + Audio (Ready to play)
    *   Video Only (No sound)
    *   Audio Only
*   **Lightweight & Fast:** Built on FastAPI for high performance and minimal overhead.
*   **CORS Enabled:** Ready to accept requests from your external PHP frontend.

## 📂 Repository Structure

*   `main.py` - The FastAPI application and yt-dlp extraction logic.
*   `requirements.txt` - Python dependencies required to run the service.

---

## 🛠️ Local Development & Testing

If you want to test the API on your local machine before deploying:

**1. Clone the repository:**
```bash
git clone [https://github.com/hamza38954017/allinvideodownloaderapi.git](https://github.com/yourusername/allinvideodownloaderapi.git)
cd dexomder-api
