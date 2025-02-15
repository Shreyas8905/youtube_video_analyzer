from flask import Flask, request, jsonify
import yt_dlp
import re
import os
import requests

app = Flask(__name__)

GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}",
    "Content-Type": "application/json"
}

def get_youtube_data(url):
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "writeautomaticsub": True, 
        "subtitleslangs": ["en"],  
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", None)
            subtitles = info.get("automatic_captions", {}).get("en", [])
            
            transcript = ""
            if subtitles:
                for sub in subtitles:
                    transcript += f"{sub.get('text', '')} "
            
            return title, transcript.strip()
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None, None

# Function to get AI-generated response
def get_bot_response(question, title, transcript):
    prompt = f"""The following is a conversation about the YouTube video titled '{title}'.
    The transcript of the video is:
    '{transcript}'
    
    Answer the user's question strictly based on the transcript. Do not answer anything unrelated.

    User: {question}
    AI:"""

    data = {
        "model": "llama3-8b-8192", 
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    response = requests.post(GROQ_API_URL, headers=HEADERS, json=data)
    response_json = response.json()

    if "choices" in response_json:
        return response_json["choices"][0]["message"]["content"].strip()
    
    return "Sorry, I couldn't generate a response."

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    youtube_url = data.get("youtube_url")
    question = data.get("question")

    if not youtube_url or not re.match(r"https?://(www\.)?youtube\.com/watch\?v=", youtube_url):
        return jsonify({"error": "Invalid YouTube URL"}), 400

    title, transcript = get_youtube_data(youtube_url)
    
    if not title or not transcript:
        return jsonify({"error": "Could not fetch video data"}), 500

    response = get_bot_response(question, title, transcript)
    return jsonify({"title": title, "answer": response})

if __name__ == "__main__":
    app.run(debug=True)
