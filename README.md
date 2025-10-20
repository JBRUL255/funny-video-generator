# 🎬 Funny Video Generator

Generates short 60s funny TikTok-style videos using:
- Pexels (royalty-free videos)
- Pixabay (royalty-free music)
- OpenAI (writes jokes)
- gTTS (voiceover)
- MoviePy (edits & exports)

## 🧰 How to Deploy on Render
1. Fork this repo to your GitHub.
2. Go to [Render.com](https://render.com) → “New +” → “Web Service”.
3. Connect your repo.
4. Set environment variables:
   - `PEXELS_API_KEY`
   - `PIXABAY_API_KEY`
   - `OPENAI_API_KEY`
5. Deploy!  
6. (Optional) Add the Worker service to run `python app.py worker`.

## 🪄 Usage
- **Enqueue a new video:**  
  `POST /enqueue` with JSON `{ "topic": "dogs at work" }`
- **Check status:**  
  `GET /job/<id>`
- **List videos:**  
  `GET /videos`
- **Download:**  
  `GET /download/<filename>`

Videos appear in `/outputs` ready for TikTok or Scoopz.
