#!/usr/bin/env python3
"""
funny-video-generator/app.py

Generates up to 5 funny short videos per day (≤60s) using:
- Pexels API (royalty-free vertical videos)
- Pixabay Music API (royalty-free background music)
- OpenAI (for jokes + scripts)
- gTTS (free TTS)
- moviepy (video assembly)
- SQLite queue system
- Flask web API
"""

import os
import io
import sys
import time
import json
import random
import sqlite3
import datetime
import threading
import requests
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Flask, request, jsonify, send_file, abort
from moviepy.editor import (
    VideoFileClip, concatenate_videoclips, AudioFileClip,
    CompositeVideoClip, TextClip, CompositeAudioClip
)
from gtts import gTTS
import openai

# ------------- CONFIG -------------
DB_PATH = "video_jobs.db"
OUTPUT_DIR = Path("outputs")
CLIPS_DIR = Path("clips_cache")
MUSIC_DIR = Path("music")
for p in (OUTPUT_DIR, CLIPS_DIR, MUSIC_DIR): p.mkdir(exist_ok=True)

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "5"))
MAX_VIDEO_DURATION = 60
VIDEO_RES = (1080, 1920)
FPS = 30

if not (PEXELS_API_KEY and PIXABAY_API_KEY and OPENAI_API_KEY):
    print("⚠️ Missing one or more API keys — set PEXELS_API_KEY, PIXABAY_API_KEY, OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# ------------- DATABASE -------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT, status TEXT, created_at TEXT, updated_at TEXT,
            attempts INTEGER DEFAULT 0, result_json TEXT, error TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT, created_at TEXT, metadata TEXT
        )
    """)
    conn.commit()
    return conn

db = init_db()
db_lock = threading.Lock()

# ------------- DB HELPERS -------------
def enqueue_job(topic):
    now = datetime.datetime.utcnow().isoformat()
    with db_lock:
        c = db.cursor()
        c.execute("INSERT INTO jobs (topic,status,created_at,updated_at) VALUES (?,?,?,?)",
                  (topic,"queued",now,now))
        db.commit()
        return c.lastrowid

def update_job(job_id, **kw):
    now = datetime.datetime.utcnow().isoformat()
    fields, vals = [], []
    for k,v in kw.items():
        fields.append(f"{k}=?")
        vals.append(v)
    fields.append("updated_at=?"); vals.append(now); vals.append(job_id)
    with db_lock:
        db.cursor().execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", vals)
        db.commit()

def get_next_job():
    with db_lock:
        c = db.cursor()
        c.execute("SELECT id,topic,status,attempts FROM jobs WHERE status='queued' ORDER BY id LIMIT 1")
        return c.fetchone()

def videos_created_today():
    today = datetime.datetime.utcnow().date().isoformat()+"T00:00:00"
    with db_lock:
        c=db.cursor()
        c.execute("SELECT COUNT(*) FROM videos WHERE created_at>=?",(today,))
        return c.fetchone()[0]

def record_video(fname, meta):
    now = datetime.datetime.utcnow().isoformat()
    with db_lock:
        db.cursor().execute("INSERT INTO videos (filename,created_at,metadata) VALUES (?,?,?)",
                            (fname,now,json.dumps(meta))); db.commit()

# ------------- PEXELS -------------
def search_pexels_videos(query):
    r=requests.get("https://api.pexels.com/videos/search",
        headers={"Authorization":PEXELS_API_KEY},
        params={"query":query,"per_page":8,"orientation":"vertical"},timeout=20)
    r.raise_for_status(); return r.json().get("videos",[])

def best_pexels_link(v):
    vids=v.get("video_files",[])
    mp4s=[x for x in vids if x.get("file_type")=="video/mp4"]
    return sorted(mp4s,key=lambda f:abs(f["width"]/f["height"]-9/16))[0]["link"]

def download_video(url,folder):
    r=requests.get(url,stream=True); r.raise_for_status()
    fname=folder/f"clip_{int(time.time()*1000)}.mp4"
    with open(fname,"wb") as f:
        for chunk in r.iter_content(8192): f.write(chunk)
    return str(fname)

# ------------- PIXABAY MUSIC -------------
def download_background_music():
    """Download 1 random track to /music if empty."""
    if list(MUSIC_DIR.glob("*.mp3")): return
    url=f"https://pixabay.com/api/audio/?key={PIXABAY_API_KEY}&q=happy&per_page=5"
    r=requests.get(url,timeout=20); r.raise_for_status()
    tracks=r.json().get("hits",[])
    if not tracks: return
    track=random.choice(tracks)
    mp3=requests.get(track["audio"],timeout=20)
    fname=MUSIC_DIR/f"bg_{int(time.time())}.mp3"
    open(fname,"wb").write(mp3.content)
    print("🎵 Downloaded background track:",fname)

# ------------- OPENAI JOKE -------------
def generate_script(topic):
    prompt=f"""
Write a funny, short (40-60s) American-style joke script for TikTok.
Output JSON: {{hook, setup, punchline, captions:[{{text,start_sec,end_sec}}]}}.
Topic: {topic}.
"""
    r=openai.ChatCompletion.create(model="gpt-4o-mini",
                                   messages=[{"role":"user","content":prompt}],
                                   max_tokens=300,temperature=0.9)
    txt=r["choices"][0]["message"]["content"]
    try: return json.loads(txt)
    except: return {"hook":topic,"setup":txt,"punchline":"","captions":[]}

# ------------- TTS -------------
def make_tts(text):
    tmp=NamedTemporaryFile(delete=False,suffix=".mp3")
    gTTS(text).write_to_fp(open(tmp.name,"wb"))
    return tmp.name

# ------------- VIDEO MAKER -------------
def make_vertical_clip(path):
    clip=VideoFileClip(path)
    clip=clip.resize(height=VIDEO_RES[1])
    if clip.w>VIDEO_RES[0]:
        clip=clip.crop(x_center=clip.w/2,width=VIDEO_RES[0])
    return clip.set_fps(FPS)

def add_captions(clip,captions):
    layers=[clip]
    for c in captions:
        txt=c.get("text")
        st=c.get("start_sec",0); en=c.get("end_sec",st+3)
        t=TextClip(txt,fontsize=56,color="white",method="caption",
                   size=(VIDEO_RES[0]-100,None)).set_position(("center","bottom")).set_start(st).set_duration(en-st)
        layers.append(t)
    return CompositeVideoClip(layers,size=VIDEO_RES).set_duration(clip.duration)

def add_music(clip,music):
    m=AudioFileClip(music)
    if m.duration<clip.duration:
        loops=int(clip.duration//m.duration)+1
        m=concatenate_videoclips([m]*loops).set_duration(clip.duration)
    else: m=m.subclip(0,clip.duration)
    m=m.volumex(0.15)
    if clip.audio:
        clip=clip.set_audio(CompositeAudioClip([clip.audio,m]))
    else: clip=clip.set_audio(m)
    return clip

def build_video(clips,script,tts_path,out_path):
    cclips=[make_vertical_clip(p).subclip(0,min(10,VideoFileClip(p).duration)) for p in clips]
    vid=concatenate_videoclips(cclips,method="compose")
    if vid.duration>MAX_VIDEO_DURATION: vid=vid.subclip(0,MAX_VIDEO_DURATION)
    voice=AudioFileClip(tts_path)
    if voice.duration>vid.duration: voice=voice.subclip(0,vid.duration)
    vid=vid.set_audio(voice)
    vid=add_captions(vid,script.get("captions",[]))
    musics=list(MUSIC_DIR.glob("*.mp3"))
    if musics: vid=add_music(vid,random.choice(musics))
    vid.write_videofile(str(out_path),codec="libx264",audio_codec="aac",fps=FPS,preset="medium")
    return str(out_path)

# ------------- JOB PROCESSOR -------------
def process_job(job_id,topic):
    update_job(job_id,status="processing")
    try:
        if videos_created_today()>=DAILY_LIMIT:
            update_job(job_id,status="error",error="Daily limit reached");return
        download_background_music()
        script=generate_script(topic)
        text=f"{script['hook']}. {script['setup']} {script['punchline']}"
        vids=search_pexels_videos(topic)
        links=[best_pexels_link(v) for v in vids[:3]]
        paths=[download_video(u,CLIPS_DIR) for u in links]
        tts=make_tts(text)
        out=OUTPUT_DIR/f"funny_{int(time.time())}.mp4"
        final=build_video(paths,script,tts,out)
        record_video(os.path.basename(final),{"topic":topic})
        update_job(job_id,status="done",result_json=json.dumps({"file":os.path.basename(final)}))
    except Exception as e:
        update_job(job_id,status="error",error=str(e))
        print("❌ Job failed:",e)

def worker_loop():
    print("Worker running...")
    while True:
        j=get_next_job()
        if j:
            jid,topic,_,_=j
            print("🎬 Processing:",topic)
            process_job(jid,topic)
        time.sleep(5)

# ------------- FLASK API -------------
app=Flask(__name__)

@app.route("/enqueue",methods=["POST"])
def enqueue():
    t=(request.json or {}).get("topic") or request.args.get("topic","funny random")
    jid=enqueue_job(t)
    return jsonify({"job_id":jid,"status":"queued"})

@app.route("/job/<int:jid>")
def job_status(jid):
    c=db.cursor();c.execute("SELECT * FROM jobs WHERE id=?",(jid,));r=c.fetchone()
    if not r: return jsonify({"error":"not found"}),404
    keys=["id","topic","status","created_at","updated_at","attempts","result_json","error"]
    return jsonify(dict(zip(keys,r)))

@app.route("/videos")
def list_videos():
    c=db.cursor();c.execute("SELECT filename,created_at FROM videos ORDER BY id DESC")
    return jsonify([{"file":f,"created":d} for f,d in c.fetchall()])

@app.route("/download/<path:name>")
def dl(name):
    p=OUTPUT_DIR/name
    if not p.exists(): abort(404)
    return send_file(str(p),as_attachment=True)

@app.route("/health")
def health(): return jsonify({"ok":True})

if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="worker": worker_loop()
    else: app.run(host="0.0.0.0",port=int(os.getenv("PORT",5000)))
