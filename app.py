import streamlit as st
import os
from dotenv import load_dotenv
from groq import Groq
import redis
import json
import time
from datetime import datetime
import hashlib

load_dotenv()

# ---------------- CONFIG ----------------
GROQ_MODEL = "llama-3.3-70b-versatile"
CACHE_TTL_SECONDS = 30 * 60
SEEN_TTL_SECONDS = 24 * 60 * 60
HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60

# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="AI BOt 2.0",
    page_icon="🤖",
    layout="centered",
)

# ---------------- CUSTOM CSS ----------------
st.markdown("""
<style>
body {
    background-color: #0f172a;
}

.main {
    background-color: #0f172a;
}

.big-title {
    font-size: 2.8rem;
    font-weight: 700;
    text-align: center;
    color: white;
    margin-bottom: 0.5rem;
}

.subtitle {
    text-align: center;
    color: #94a3b8;
    margin-bottom: 2rem;
}

.glass-card {
    background: rgba(255,255,255,0.05);
    padding: 2rem;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 30px rgba(0,0,0,0.3);
}
</style>
""", unsafe_allow_html=True)

# ---------------- GROQ CLIENT ----------------
@st.cache_resource
def get_groq_client():
    return Groq(api_key=os.getenv("GROQ_API_KEY"))

groq_client = get_groq_client()

# ---------------- REDIS CLIENT ----------------
@st.cache_resource
def get_redis_client():
    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True
        )
        client.ping()
        return client
    except:
        return None

redis_client = get_redis_client()

# ---------------- HELPERS ----------------
def make_query_hash(q: str) -> str:
    cleaned = " ".join(q.strip().lower().split())
    return hashlib.sha256(cleaned.encode()).hexdigest()[:16]

# ---------------- SESSION ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None

VALID_USERS = {
    "sumit": "1234",
    "demo": "demo2025",
}

def authenticate(username, password):
    return VALID_USERS.get(username.strip().lower()) == password

# ---------------- HEADER ----------------
st.markdown('<div class="big-title">🤖 QueryBot AI</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Fast Answers • Smart Caching • Powered by Groq</div>', unsafe_allow_html=True)

# ---------------- LOGIN ----------------
if not st.session_state.authenticated:
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("Sign In")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if st.button("Login", use_container_width=True):
            if authenticate(username, password):
                st.session_state.username = username.strip().lower()
                st.session_state.authenticated = True
                st.success("Login successful!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Invalid credentials")

        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

USERNAME = st.session_state.username

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.markdown("### 👤 User")
    st.success(f"Logged in as **{USERNAME}**")

    if st.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ---------------- CHAT ----------------
st.markdown("### 💬 Ask Anything")

question = st.chat_input("Type your question here...")

if question:
    with st.chat_message("user"):
        st.markdown(question)

    q_hash = make_query_hash(question)
    summary_key = f"cache:{USERNAME}:{q_hash}"

    cached = None
    if redis_client:
        cached = redis_client.get(summary_key)

    if cached:
        with st.chat_message("assistant"):
            st.markdown(cached)
    else:
        with st.spinner("Thinking..."):
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": question}],
                temperature=0.7,
            )
            answer = response.choices[0].message.content.strip()

            if redis_client:
                redis_client.setex(summary_key, CACHE_TTL_SECONDS, answer)

        with st.chat_message("assistant"):
            st.markdown(answer)