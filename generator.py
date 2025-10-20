import os, random, requests, tempfile
from pathlib import Path
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
import cloudinary, cloudinary.uploader

# === Ensure directories exist ===
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
VIDEO_DIR = STATIC_DIR / "videos"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# === Environment setup ===
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL")

if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL)

MOCK_VIDEOS = [
    "https://sample-videos.com/video123/mp4/360/sample-5s.mp4",
    "https://sample-videos.com/video123/mp4/360/big_buck_bunny_360p_1mb.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-10s.mp4"
]

def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return dest

def get_background_music():
    if not PIXABAY_API_KEY:
        return None
    try:
        res = requests.get(
            f"https://pixabay.com/api/?key={PIXABAY_API_KEY}&q=funny&media_type=music&per_page=5"
        ).json()
        hits = res.get("hits", [])
        if not hits:
            return None
        return hits[0]["audio"]
    except Exception as e:
        print("Pixabay error:", e)
        return None

def generate_final_video():
    base_url = random.choice(MOCK_VIDEOS)
    filename = f"funny_{random.randint(1000,9999)}.mp4"
    local_path = VIDEO_DIR / filename
    temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name

    # Download video
    download_file(base_url, temp_video)

    # Compose with background music
    clip = VideoFileClip(temp_video).resize(height=720)
    audio_url = get_background_music()
    if audio_url:
        temp_audio = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
        download_file(audio_url, temp_audio)
        bg_audio = AudioFileClip(temp_audio).volumex(0.2)
        clip = clip.set_audio(bg_audio)
    clip.write_videofile(str(local_path), codec="libx264", audio_codec="aac", threads=2, logger=None)

    # Upload to Cloudinary
    cloud_url = None
    if CLOUDINARY_URL:
        try:
            upload_res = cloudinary.uploader.upload(str(local_path), resource_type="video")
            cloud_url = upload_res.get("secure_url")
        except Exception as e:
            print("Cloudinary upload failed:", e)

    return filename, cloud_url
