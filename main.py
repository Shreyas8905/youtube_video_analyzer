from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import re
import yt_dlp
import requests
import os
from youtube_transcript_api import YouTubeTranscriptApi

app = Flask(__name__)
app.secret_key = "your_secret_key"

GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

def init_db():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats 
                 (id INTEGER PRIMARY KEY, video_title TEXT, user_message TEXT, bot_response TEXT)''')
    conn.commit()
    conn.close()

init_db()

def get_youtube_info(url):
    video_id = url.split("v=")[-1].split("&")[0]  

    ydl_opts = {"quiet": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            title = info.get("title", "Unknown Title")
        except Exception as e:
            print(f"Error fetching title: {e}")
            return None, None

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([entry["text"] for entry in transcript_list])
    except Exception as e:
        print(f"Error fetching transcript: {e}")
        transcript_text = None

    return title, transcript_text


def get_bot_response(user_input, video_title, transcript):
    """Generates chatbot responses using Groq's Llama 3 API, restricting answers to the transcript."""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""You are an AI assistant that only answers questions based on the transcript of the YouTube video titled "{video_title}".
    Do not provide any information that is not found in the transcript.

    Transcript: {transcript}

    User: {user_input}
    AI:"""
    
    data = {
        "model": "llama3-8b-8192",
        "messages": [{"role": "system", "content": "You are a helpful AI assistant."},
                     {"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    response = requests.post(GROQ_API_URL, json=data, headers=headers)
    
    if response.status_code != 200:
        return f"Error: Groq API returned {response.status_code} - {response.text}"
    
    response_json = response.json()

    if "choices" not in response_json:
        return f"Unexpected API Response: {response_json}"

    return response_json["choices"][0]["message"]["content"].strip()


@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        url = request.form["youtube_url"]
        if not re.match(r"https?://(www\.)?youtube\.com/watch\?v=", url):
            return render_template("home.html", error="Invalid YouTube URL")
        
        title, transcript = get_youtube_info(url)
        if title and transcript:
            session["video_title"] = title  
            session["transcript"] = transcript  
            return redirect(url_for("confirm"))

        return render_template("home.html", error="Could not fetch video title or transcript")

    return render_template("home.html")

@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    if "video_title" not in session:  
        return redirect(url_for("home"))  

    title = session["video_title"]  

    if request.method == "POST":  
        return redirect(url_for("chat"))  

    return render_template("confirm.html", video_title=title)  


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "video_title" not in session:
        return redirect(url_for("home"))

    video_title = session["video_title"]
    trascription = session["transcript"]

    if request.method == "POST":
        user_message = request.form["message"]
        response = get_bot_response(user_message, video_title, trascription)

        conn = sqlite3.connect("chat.db")
        c = conn.cursor()
        c.execute("INSERT INTO chats (video_title, user_message, bot_response) VALUES (?, ?, ?)",
                  (video_title, user_message, response))
        conn.commit()
        conn.close()

        return response

    return render_template("chat.html", video_title=video_title)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
