import streamlit as st
import os
from dotenv import load_dotenv
from groq import Groq
import redis
import hashlib
import time

load_dotenv()

# ---------------- CONFIG ----------------
GROQ_MODEL = "llama-3.3-70b-versatile"
CACHE_TTL_SECONDS = 30 * 60
MAX_WORD_LIMIT = 100
COST_PER_1K_TOKENS = 0.002  # Example cost (edit according to real pricing)

# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="AI Bot 2.0",
    page_icon="🤖",
    layout="centered",
)

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

def limit_words(text, max_words):
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return text

# ---------------- SESSION INIT ----------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "total_session_tokens" not in st.session_state:
    st.session_state.total_session_tokens = 0

# ---------------- LOGIN ----------------
VALID_USERS = {
    "sumit": "1234",
    "demo": "demo2025",
}

def authenticate(username, password):
    return VALID_USERS.get(username.strip().lower()) == password

# ---------------- HEADER ----------------
st.title("🤖 QueryBot 2.O")
st.caption("Fast Answers • Smart Caching • Made by Sumit ")

# ---------------- LOGIN UI ----------------
if not st.session_state.authenticated:
    st.subheader("Sign In")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if authenticate(username, password):
            st.session_state.username = username.strip().lower()
            st.session_state.authenticated = True
            st.success("Login successful!")
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("Invalid credentials")

    st.stop()

USERNAME = st.session_state.username

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.success(f"Logged in as {USERNAME}")
    st.markdown(f"### 🪙 Total Session Tokens: {st.session_state.total_session_tokens}")

    estimated_cost = (st.session_state.total_session_tokens / 1000) * COST_PER_1K_TOKENS
    st.markdown(f"💰 Estimated Cost: ${estimated_cost:.6f}")

    if st.button("🗑 Clear Chat"):
        st.session_state.messages = []
        st.session_state.total_session_tokens = 0
        st.rerun()

    if st.button("Logout"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()

# ---------------- DISPLAY OLD MESSAGES ----------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---------------- CHAT INPUT ----------------
question = st.chat_input("Type your question here...")

if question:

    with st.chat_message("user"):
        st.markdown(question)

    st.session_state.messages.append(
        {"role": "user", "content": question}
    )

    q_hash = make_query_hash(question)
    cache_key = f"cache:{USERNAME}:{q_hash}"

    cached = None
    if redis_client:
        cached = redis_client.get(cache_key)

    if cached:
        answer = cached
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
    else:
        with st.spinner("Thinking..."):
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a helpful assistant. Always respond clearly and limit your answer to maximum {MAX_WORD_LIMIT} words."
                    }
                ] + st.session_state.messages,
                temperature=0.7,
            )

            answer = response.choices[0].message.content.strip()
            answer = limit_words(answer, MAX_WORD_LIMIT)

            # Token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            st.session_state.total_session_tokens += total_tokens

            if redis_client:
                redis_client.setex(cache_key, CACHE_TTL_SECONDS, answer)

    with st.chat_message("assistant"):
        st.markdown(answer)

        if total_tokens > 0:
            st.caption(
                f"🪙 Tokens → Input: {prompt_tokens} | Output: {completion_tokens} | Total: {total_tokens}"
            )

    st.session_state.messages.append(
        {"role": "assistant", "content": answer}
    )