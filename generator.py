import os
import random
import requests
import tempfile
from pathlib import Path
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip
from dotenv import load_dotenv
import cloudinary
import cloudinary.uploader

load_dotenv()

# === ENVIRONMENT ===
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

VIDEO_DIR = Path("static/videos")
AUDIO_DIR = Path("static/music")

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True
)

# === FETCH VIDEO FROM PIXABAY ===
def get_pixabay_video():
    url = f"https://pixabay.com/api/videos/?key={PIXABAY_API_KEY}&q=funny&per_page=50"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        if not hits:
            raise ValueError("No Pixabay videos found.")
        return random.choice(hits)["videos"]["medium"]["url"]
    except Exception as e:
        print(f"[ERROR] Pixabay fetch failed: {e}")
        return None


def download_file(url, suffix):
    for attempt in range(3):
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            for chunk in r.iter_content(1024 * 1024):
                temp.write(chunk)
            temp.close()
            return temp.name
        except Exception as e:
            print(f"[Retry {attempt+1}/3] Download failed: {e}")
    raise ConnectionError(f"Failed to download {url}")


# === MAIN VIDEO CREATION ===
def generate_final_video(joke_text="Why did the cat sit on the computer? To keep an eye on the mouse!"):
    print("[INFO] Starting funny video generation...")
    try:
        video_url = get_pixabay_video()
        if not video_url:
            raise ValueError("No valid video source")

        video_path = download_file(video_url, ".mp4")
        music_url = "https://cdn.pixabay.com/download/audio/2023/07/05/audio_62b5b6e7ae.mp3"
        music_path = download_file(music_url, ".mp3")

        clip = VideoFileClip(video_path).subclip(0, 60)
        clip = clip.resize(height=1080)

        # Add caption text
        text_clip = TextClip(
            joke_text,
            fontsize=70,
            color="white",
            font="Arial-Bold",
            method="caption",
            size=(clip.w - 100, None)
        ).set_position(("center", "bottom")).set_duration(clip.duration)

        audio_clip = AudioFileClip(music_path).volumex(0.2)
        final = CompositeVideoClip([clip, text_clip])
        final = final.set_audio(audio_clip)

        output_path = VIDEO_DIR / f"funny_{random.randint(1000,9999)}.mp4"
        final.write_videofile(str(output_path), fps=24, codec="libx264", audio_codec="aac")

        # === Upload to Cloudinary ===
        upload_result = cloudinary.uploader.upload_large(
            str(output_path),
            resource_type="video",
            folder="funny_videos/"
        )

        print("[UPLOAD SUCCESS]", upload_result["secure_url"])
        return upload_result["secure_url"]

    except Exception as e:
        print(f"[ERROR] Video generation failed: {e}")
        return None
