import os, random, time, requests
from pathlib import Path
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip, CompositeAudioClip, TextClip, CompositeVideoClip
from gtts import gTTS
import cloudinary.uploader
import tempfile

VIDEO_DIR = Path("static/videos")
VIDEO_DIR.mkdir(exist_ok=True)

# small set of 360p short royalty-free clips as defaults (fast)
DEFAULT_CLIPS = [
    "https://sample-videos.com/video123/mp4/360/big_buck_bunny_360p_5mb.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-5s.mp4",
    "https://sample-videos.com/video123/mp4/360/sample-10s.mp4"
]

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    import openai
    openai.api_key = OPENAI_API_KEY

# helper: download url to local path
def download_to(path, url, timeout=25):
    r = requests.get(url, stream=True, timeout=timeout)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return path

# fetch small pixabay audio track (mp3) — returns local path or None
def fetch_pixabay_music():
    if not PIXABAY_API_KEY:
        return None
    try:
        url = f"https://pixabay.com/api/audio/?key={PIXABAY_API_KEY}&q=upbeat&per_page=10"
        r = requests.get(url, timeout=10); r.raise_for_status()
        data = r.json()
        hits = data.get("hits") or []
        if not hits:
            return None
        sel = random.choice(hits)
        audio_url = sel.get("audio")
        if not audio_url:
            return None
        dest = VIDEO_DIR / f"music_{int(time.time())}.mp3"
        download_to(dest, audio_url)
        return str(dest)
    except Exception:
        return None

# generate short script via OpenAI if available, else simple fallback
def build_script(topic="funny"):
    if OPENAI_API_KEY:
        try:
            prompt = f"Write a 2-line hook+one-sentence punchline (3-30 words total) for a short TikTok-style funny video about '{topic}'. Return plain text."
            res = openai.ChatCompletion.create(model="gpt-4o-mini", messages=[{"role":"user","content":prompt}], max_tokens=60, temperature=0.9)
            text = res["choices"][0]["message"]["content"].strip().replace("\n"," ")
            return text
        except Exception:
            pass
    # fallback
    return f"{topic.capitalize()} be like: when life gives you {topic}… funny moment."

# small function to overlay captions
def overlay_captions(clip, text):
    txt = TextClip(text, fontsize=56, method="caption", size=(clip.w-80, None))
    txt = txt.set_position(("center", clip.h - 220)).set_duration(clip.duration).crossfadein(0.1).crossfadeout(0.1)
    return CompositeVideoClip([clip, txt], size=(clip.w, clip.h))

# main function: returns dict {filename, local_path, cloud_url}
def generate_final_video(progress_cb=lambda m: None):
    try:
        progress_cb("building script")
        script_text = build_script("funny")
        progress_cb("script ready")

        # get 2-3 short clips (download)
        progress_cb("selecting clips")
        clips_sources = DEFAULT_CLIPS[:]
        random.shuffle(clips_sources)
        clips_local = []
        for i, url in enumerate(clips_sources[:3]):
            progress_cb(f"downloading clip {i+1}")
            tmpf = VIDEO_DIR / f"clip_{int(time.time())}_{i}.mp4"
            download_to(tmpf, url)
            clips_local.append(str(tmpf))

        # TTS
        progress_cb("generating voice (TTS)")
        tts_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts = gTTS(script_text, lang="en")
        tts.write_to_fp(open(tts_tmp.name, "wb"))

        # background music (pixabay)
        progress_cb("fetching background music")
        music_path = fetch_pixabay_music()

        # assemble with moviepy
        progress_cb("assembling video (moviepy)")
        vclips = []
        total_dur = 0
        for p in clips_local:
            vc = VideoFileClip(p)
            # limit each to 8-12s for punchiness
            sub_dur = min(10, vc.duration)
            vc = vc.subclip(0, sub_dur).resize(height=1920)  # vertical target height
            # crop/pad to 1080x1920
            if vc.w > 1080:
                vc = vc.crop(x_center=vc.w/2, width=1080)
            else:
                vc = vc.on_color(size=(1080,vc.h), color=(0,0,0), pos=("center","center"))
            vclips.append(vc)
            total_dur += vc.duration
            if total_dur >= 55:
                break

        final = concatenate_videoclips(vclips, method="compose")
        if final.duration > 60:
            final = final.subclip(0, 60)

        # overlay captions
        final = overlay_captions(final, script_text)

        # prepare voice & music audio
        voice = AudioFileClip(tts_tmp.name)
        if voice.duration > final.duration:
            voice = voice.subclip(0, final.duration)
        # mix with music
        if music_path:
            music = AudioFileClip(music_path)
            if music.duration < final.duration:
                # loop
                loops = int(final.duration // music.duration) + 1
                mus = concatenate_videoclips([music]*loops).set_duration(final.duration)
                music = mus
            else:
                music = music.subclip(0, final.duration)
            music = music.volumex(0.12)
            combined_audio = CompositeAudioClip([voice.volumex(1.0), music])
        else:
            combined_audio = voice

        final = final.set_audio(combined_audio)

        # write final file
        fname = f"funny_{int(time.time())}_{random.randint(0,9999)}.mp4"
        outpath = VIDEO_DIR / fname
        progress_cb("exporting final mp4 (this can take a few seconds)")
        final.write_videofile(str(outpath), codec="libx264", audio_codec="aac", threads=2, fps=24, preset="medium")
        progress_cb("export complete")

        cloud_url = None
        # Cloudinary upload if configured
        cloud_url = try_upload_cloudinary(outpath)

        return {"filename": fname, "local_path": str(outpath), "cloud_url": cloud_url}
    except Exception as e:
        raise

def try_upload_cloudinary(path):
    try:
        import cloudinary
        import cloudinary.uploader
        # cloudinary.config from CLOUDINARY_URL env var is automatic when using cloudinary.uploader
        res = cloudinary.uploader.upload(str(path), resource_type="video", folder="funny_videos", public_id=Path(path).stem)
        return res.get("secure_url")
    except Exception:
        return None
