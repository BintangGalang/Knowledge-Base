import streamlit as st
import os
import sys
import base64
from dotenv import load_dotenv

# ── Setup Path ────────────────────────────────────────────────────────────────
root_path = os.path.abspath(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

load_dotenv()

from src.retrieval.retriever import Retriever
from src.generation.generator import Generator

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SHAVIRA – Undiksha Virtual Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── HELPER ────────────────────────────────────────────────────────────────────
def img_to_b64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

avatar_path = os.path.join(root_path, "assets", "shavira_avatar.png")
avatar_b64  = img_to_b64(avatar_path)

# ── GLOBAL CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800&display=swap');

/* ══════════════════════════ BASE ══════════════════════════ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    background-color: #0d0d0d !important;
    color: #e2e2e2 !important;
}

/* Strip ALL Streamlit chrome */
#MainMenu, footer, header, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"] {
    display: none !important;
}

/* Remove ALL default padding/margin from main container */
.main .block-container,
[data-testid="block-container"],
.stMainBlockContainer {
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
}

section[data-testid="stMain"] {
    padding: 0 !important;
    overflow-x: hidden;
}

/* ══════════════════════════ SIDEBAR ══════════════════════════ */
[data-testid="stSidebar"] {
    background: #111111 !important;
    border-right: 1px solid #1f1f1f !important;
    width: 230px !important;
    min-width: 230px !important;
    max-width: 230px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}
[data-testid="stSidebar"] section {
    padding: 0 !important;
}

/* Sidebar "Chat Baru" button */
[data-testid="stSidebar"] .stButton > button {
    background: #1e1e1e !important;
    border: 1px solid #2c2c2c !important;
    color: #bbb !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    border-radius: 8px !important;
    padding: 10px 16px !important;
    width: calc(100% - 24px) !important;
    margin: 0 12px !important;
    transition: all 0.18s !important;
    cursor: pointer !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #252535 !important;
    border-color: #4a7aff !important;
    color: #fff !important;
}

/* ══════════════════════════ HEADER ══════════════════════════ */
.s-header {
    background: #111111;
    border-bottom: 1px solid #1f1f1f;
    padding: 14px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 200;
    height: 60px;
}
.s-header-center {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
    justify-content: center;
}
.s-header-center .uni-logo {
    width: 36px; height: 36px;
    border-radius: 50%;
    background: #1e3a8a;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; flex-shrink: 0;
}
.s-header-center .app-title {
    font-size: 16px;
    font-weight: 700;
    color: #f0f0f0;
    letter-spacing: -0.02em;
}
.s-header-right {
    display: flex;
    align-items: center;
    gap: 12px;
}
.s-user-info { text-align: right; }
.s-user-name  { font-size: 13px; font-weight: 600; color: #fff; line-height: 1.3; }
.s-user-email { font-size: 11px; color: #666; }
.s-user-badge {
    width: 38px; height: 38px; border-radius: 50%;
    background: linear-gradient(135deg, #d97706, #f59e0b);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 16px; color: #fff;
    flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(217,119,6,0.3);
}

/* ══════════════════════════ WELCOME SCREEN ══════════════════════════ */
.welcome-page {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 140px);
    padding: 40px 24px 120px;
    text-align: center;
}
.s-avatar-ring {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    border: 4px solid #4a7aff;
    overflow: hidden;
    box-shadow:
        0 0 0 10px rgba(74,122,255,0.08),
        0 0 50px rgba(74,122,255,0.4),
        0 20px 60px rgba(0,0,0,0.5);
    transition: transform 0.35s ease, box-shadow 0.35s ease;
    margin-bottom: 28px;
    cursor: default;
}
.s-avatar-ring:hover {
    transform: scale(1.05) translateY(-4px);
    box-shadow:
        0 0 0 12px rgba(74,122,255,0.12),
        0 0 70px rgba(74,122,255,0.5),
        0 28px 80px rgba(0,0,0,0.6);
}
.s-avatar-ring img {
    width: 100%; height: 100%; object-fit: cover;
}
.s-greeting-main {
    font-size: 36px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin-bottom: 8px;
}
.s-greeting-sub {
    font-size: 26px;
    font-weight: 600;
    color: #c8c8c8;
    letter-spacing: -0.02em;
    margin-bottom: 12px;
}
.s-greeting-desc {
    font-size: 16px;
    color: #666;
    margin-bottom: 40px;
}

/* ══════════════════════════ SUGGESTION BUTTONS ══════════════════════════ */
.s-suggestions {
    width: 100%;
    max-width: 820px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
}
.s-suggestions .stButton > button {
    background: #181818 !important;
    border: 1px solid #262626 !important;
    border-radius: 14px !important;
    padding: 18px 20px !important;
    font-size: 15px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    color: #c8c8c8 !important;
    text-align: center !important;
    line-height: 1.5 !important;
    min-height: 80px !important;
    white-space: normal !important;
    width: 100% !important;
    transition: all 0.22s ease !important;
    cursor: pointer !important;
}
.s-suggestions .stButton > button:hover {
    background: #1d1d30 !important;
    border-color: #4a7aff !important;
    color: #ffffff !important;
    box-shadow: 0 0 20px rgba(74,122,255,0.2), 0 4px 16px rgba(0,0,0,0.3) !important;
    transform: translateY(-3px) !important;
}
.s-suggestions .stButton > button:active {
    transform: translateY(-1px) !important;
}

/* ══════════════════════════ CHAT AREA ══════════════════════════ */
.s-chat-wrap {
    width: 100%;
    max-width: 840px;
    margin: 0 auto;
    padding: 32px 28px 120px;
}
.s-msg-user {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 20px;
}
.s-msg-bot {
    display: flex;
    justify-content: flex-start;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 20px;
}
.s-bubble-user {
    background: linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%);
    color: #fff;
    border-radius: 20px 20px 4px 20px;
    padding: 14px 20px;
    max-width: 70%;
    font-size: 15px;
    line-height: 1.65;
    box-shadow: 0 4px 20px rgba(29,78,216,0.35);
    word-wrap: break-word;
}
.s-bubble-bot {
    background: #181818;
    border: 1px solid #242424;
    color: #e2e2e2;
    border-radius: 4px 20px 20px 20px;
    padding: 14px 20px;
    max-width: 70%;
    font-size: 15px;
    line-height: 1.65;
    word-wrap: break-word;
}
.s-bot-icon {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    overflow: hidden;
    flex-shrink: 0;
    border: 2px solid #4a7aff;
    box-shadow: 0 0 14px rgba(74,122,255,0.3);
}
.s-bot-icon img { width: 100%; height: 100%; object-fit: cover; }

/* ══════════════════════════ CHAT INPUT ══════════════════════════ */
[data-testid="stChatInput"] {
    position: fixed !important;
    bottom: 0 !important;
    left: 230px !important;
    right: 0 !important;
    width: auto !important;
    background: #0f0f0f !important;
    border-top: 1px solid #1f1f1f !important;
    padding: 16px 24px !important;
    z-index: 150 !important;
}
[data-testid="stChatInputTextArea"] {
    background: #181818 !important;
    border: 2px solid #2a2a2a !important;
    border-radius: 16px !important;
    color: #e2e2e2 !important;
    font-size: 15px !important;
    font-family: 'Inter', sans-serif !important;
    padding: 16px 20px !important;
    min-height: 56px !important;
    resize: none !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
    max-width: 840px !important;
    margin: 0 auto !important;
    display: block !important;
}
[data-testid="stChatInputTextArea"]:focus {
    border-color: #4a7aff !important;
    box-shadow: 0 0 0 4px rgba(74,122,255,0.15) !important;
    outline: none !important;
}
[data-testid="stChatInputSubmitButton"] {
    background: #4a7aff !important;
    border-radius: 12px !important;
    border: none !important;
}

/* ══════════════════════════ SIDEBAR NAV ══════════════════════════ */
.s-nav-brand {
    padding: 22px 18px 16px;
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
    border-bottom: 1px solid #1f1f1f;
    margin-bottom: 12px;
    letter-spacing: -0.02em;
}
.s-nav-item {
    padding: 11px 18px;
    font-size: 14px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 10px;
    border-radius: 9px;
    margin: 2px 10px;
    cursor: pointer;
    transition: background 0.18s, color 0.18s;
    line-height: 1;
}
.s-nav-item:hover  { background: #1c1c1c; color: #ddd; }
.s-nav-item.active { background: #1a1a2e; color: #7fa5ff; font-weight: 600; }
.s-nav-item.green  { color: #34d399; }
.s-nav-item.red    { color: #f87171; }
.s-nav-footer {
    position: absolute;
    bottom: 20px;
    left: 18px;
    font-size: 11px;
    color: #3a3a3a;
    line-height: 1.8;
}
.s-nav-footer strong { color: #555; }

/* ══════════════════════════ EXPANDER ══════════════════════════ */
[data-testid="stExpander"] {
    background: #161616 !important;
    border: 1px solid #222 !important;
    border-radius: 12px !important;
    margin: 8px 0 !important;
}

/* ══════════════════════════ SPINNER ══════════════════════════ */
[data-testid="stSpinner"] { color: #4a7aff !important; }

/* ══════════════════════════ SCROLLBAR ══════════════════════════ */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #111; }
::-webkit-scrollbar-thumb { background: #2a2a2a; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3a3a3a; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "retriever" not in st.session_state:
    db_path = os.path.join(root_path, "storage", "faiss_db")
    try:
        st.session_state.retriever = Retriever(db_path=db_path)
        st.session_state.generator = Generator(model_name="gpt-4o-mini")
    except Exception as e:
        st.error(f"❌ Gagal memuat database: {e}\n\nJalankan ingestion pipeline terlebih dahulu.")
        st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="s-nav-brand">🤖 Shavira</div>', unsafe_allow_html=True)

    if st.button("＋  Chat Baru", key="btn_new_chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("""
    <div class="s-nav-item active">💬&nbsp;&nbsp;Layar Chat</div>
    <div class="s-nav-item">ℹ️&nbsp;&nbsp;About&nbsp;&nbsp;˅</div>
    <div class="s-nav-item green">📋&nbsp;&nbsp;Feedback</div>
    <div class="s-nav-item red">↩&nbsp;&nbsp;Keluar</div>
    <div class="s-nav-footer">
        <strong>SHAVIRA</strong><br>
        RG-Generative AI &amp; UPA TIK<br>
        Undiksha<br>
        resika@undiksha.ac.id
    </div>
    """, unsafe_allow_html=True)

# ── HEADER ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="s-header">
    <div style="width:120px;"></div>
    <div class="s-header-center">
        <div class="uni-logo">🎓</div>
        <span class="app-title">Undiksha Virtual Assistant (SHAVIRA)</span>
    </div>
    <div class="s-header-right">
        <div class="s-user-info">
            <div class="s-user-name">17_Ketut Bintang Galang Putra</div>
            <div class="s-user-email">bintang.galang@student.undiksha.ac.id</div>
        </div>
        <div class="s-user-badge">G</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── SUGGESTIONS ───────────────────────────────────────────────────────────────
SUGGESTIONS = [
    "Apa Makna Salam Harmoni!",
    "Kapan Pengumuman SNBT?",
    "Apa saja jalur SMBJM 2026?",
    "Kapan Jadwal UAS?",
    "Bagaimana prosedur cuti akademik?",
    "Apa saja informasi yang dikecualikan?",
]

# ── MAIN CONTENT ──────────────────────────────────────────────────────────────
if not st.session_state.messages:

    avatar_html = (
        f'<img src="data:image/png;base64,{avatar_b64}" alt="Shavira"/>'
        if avatar_b64 else "🤖"
    )

    st.markdown(f"""
    <div class="welcome-page">
        <div class="s-avatar-ring">{avatar_html}</div>
        <div class="s-greeting-main">Salam Harmoni!</div>
        <div class="s-greeting-sub">Hai, saya Shavira</div>
        <div class="s-greeting-desc">Silakan tanyakan apapun tentang Undiksha :-)</div>
    </div>
    """, unsafe_allow_html=True)

    # Suggestion buttons — centered via columns
    _, mid, _ = st.columns([1, 4, 1])
    with mid:
        st.markdown('<div class="s-suggestions">', unsafe_allow_html=True)
        cols = st.columns(3, gap="medium")
        for i, sug in enumerate(SUGGESTIONS):
            with cols[i % 3]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": sug})
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # ── CHAT VIEW ─────────────────────────────────────────────────────────────
    st.markdown('<div class="s-chat-wrap">', unsafe_allow_html=True)

    icon_html = (
        f'<img src="data:image/png;base64,{avatar_b64}" alt="Shavira"/>'
        if avatar_b64 else "🤖"
    )

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="s-msg-user">
                <div class="s-bubble-user">{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="s-msg-bot">
                <div class="s-bot-icon">{icon_html}</div>
                <div class="s-bubble-bot">{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)

            if msg.get("references"):
                with st.expander("📄 Lihat Sumber Referensi"):
                    st.markdown(msg["references"])

    st.markdown('</div>', unsafe_allow_html=True)

# ── CHAT INPUT ────────────────────────────────────────────────────────────────
if prompt := st.chat_input("Tanyakan sesuatu tentang Undiksha..."):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.spinner("⏳ Shavira sedang mencari jawaban..."):
        nodes = st.session_state.retriever.search(prompt)

        if nodes:
            response = st.session_state.generator.generate(prompt, nodes)

            ref_text = ""
            for i, node in enumerate(nodes):
                fname = node.metadata.get("title", "Unknown")
                chunk_index  = node.metadata.get("chunk_index", "?")
                total_chunks  = node.metadata.get("total_chunks", "?")
                category = node.metadata.get("category", "")
                chunk = node.get_content() if hasattr(node, "get_content") else getattr(node, "text", "")
                ref_text += f"**Sumber {i+1}: {fname} (Bagian {chunk_index} dari {total_chunks}) - {category}**\n```text\n{chunk}\n```\n---\n"

            st.session_state.messages.append({
                "role": "assistant",
                "content": str(response),
                "references": ref_text,
            })
        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Maaf, saya tidak menemukan informasi tersebut dalam dokumen saya.",
                "references": "",
            })

    st.rerun()