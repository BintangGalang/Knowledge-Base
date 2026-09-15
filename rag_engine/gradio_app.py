"""
SHAVIRA – Gradio App
Run: python gradio_app.py
"""
import os
import sys
import base64

# ── WAJIB SEBELUM IMPORT APAPUN: paksa offline mode ───────────────────────────
os.environ["TRANSFORMERS_OFFLINE"]  = "1"
os.environ["HF_HUB_OFFLINE"]        = "1"
os.environ["HF_DATASETS_OFFLINE"]   = "1"

# ── Setup Path ─────────────────────────────────────────────────────────────────
root_path = os.path.abspath(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from dotenv import load_dotenv
load_dotenv()

import gradio as gr
from src.retrieval.retriever import Retriever
from src.generation.generator import Generator

# ── Avatar ─────────────────────────────────────────────────────────────────────
avatar_path = os.path.join(root_path, "assets", "shavira_avatar.png")

def img_to_b64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

avatar_b64 = img_to_b64(avatar_path)
avatar_uri = f"data:image/png;base64,{avatar_b64}" if avatar_b64 else ""

# Default User Avatar SVG
user_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%23ffffff"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>'
user_avatar_uri = f"data:image/svg+xml,{user_svg}"

# ── Init RAG ───────────────────────────────────────────────────────────────────
print("Memuat model embedding dari cache lokal...")
retriever = Retriever(db_path=os.path.join(root_path, "storage", "faiss_db"))
generator = Generator(model_name="gpt-4o-mini")
print("SHAVIRA siap!")

# ── Suggestion questions ───────────────────────────────────────────────────────
SUGGESTIONS = [
    "Apa Makna Salam Harmoni!",
    "Kapan Pengumuman SNBT?",
    "Apa saja jalur SMBJM 2026?",
    "Kapan Jadwal UAS?",
    "Bagaimana prosedur cuti akademik?",
    "Apa saja informasi yang dikecualikan?",
]

# ── Chat function ──────────────────────────────────────────────────────────────
def respond(message: str, history: list):
    message = message.strip()
    if not message:
        return history, ""

    nodes = retriever.search(message)
    if not nodes:
        answer = "Maaf, saya tidak menemukan informasi tersebut dalam dokumen saya."
    else:
        response = generator.generate(message, nodes)
        answer = str(response)

        refs = "\n\n---\n**📄 Sumber Referensi:**"
        for i, node in enumerate(nodes):
            fname = node.metadata.get("file_name", "Unknown")
            page  = node.metadata.get("page_label", "?")
            refs += f"\n- **[{i+1}]** {fname} — Hal. {page}"
        answer += refs

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})
    return history, ""

# ── Custom CSS ─────────────────────────────────────────────────────────────────
avatar_img_tag = f'<img src="{avatar_uri}" alt="Shavira" style="width:100%;height:100%;object-fit:cover"/>' if avatar_uri else "🤖"

CSS = f"""
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Base */
*, *::before, *::after {{ box-sizing: border-box; }}
body, .gradio-container, #root {{
    font-family: 'Inter', sans-serif !important;
    background: #0d0d0d !important;
    color: #e2e2e2 !important;
    margin: 0 !important; padding: 0 !important;
}}
footer, .built-with, .svelte-1ipelgc {{ display: none !important; }}

/* Remove all Gradio default paddings */
.gradio-container {{
    max-width: 100% !important;
    padding: 0 !important;
    min-height: 100vh;
}}
.main {{
    padding: 0 !important;
    gap: 0 !important;
}}
.contain {{ padding: 0 !important; }}

/* ═══ Header ═══ */
#shavira-header {{
    background: #111;
    border-bottom: 1px solid #1e1e1e;
    padding: 14px 32px;
    display: flex; align-items: center; justify-content: space-between;
    height: 64px;
}}
#shavira-header > div {{ flex: 1; }}
#shavira-header .center {{
    display: flex; align-items: center; justify-content: center; gap: 12px;
}}
#shavira-header .logo {{
    width: 38px; height: 38px; border-radius: 50%;
    background: #1e3a8a; display: flex; align-items: center; justify-content: center;
    font-size: 20px;
}}
#shavira-header .title {{
    font-size: 16px; font-weight: 700; color: #f0f0f0;
    letter-spacing: -0.02em; white-space: nowrap;
}}
#shavira-header .right {{
    display: flex; align-items: center; gap: 12px; margin-left: auto;
}}
.user-info {{ text-align: right; }}
.user-info .name {{ font-size: 13px; font-weight: 600; color: #f0f0f0; line-height: 1.3; }}
.user-info .email {{ font-size: 11px; color: #555; }}
.user-badge {{
    width: 40px; height: 40px; border-radius: 50%;
    background: linear-gradient(135deg, #d97706, #f59e0b);
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 17px; color: #fff;
    box-shadow: 0 0 0 3px rgba(217,119,6,0.25);
}}

/* ═══ Welcome section ═══ */
#welcome-section {{
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 48px 24px 24px; text-align: center;
}}
.avatar-ring {{
    width: 200px; height: 200px; border-radius: 50%;
    border: 5px solid #4a7aff; overflow: hidden;
    box-shadow: 0 0 20px rgba(74,122,255,0.2),
                0 10px 30px rgba(0,0,0,0.5);
    margin-bottom: 24px; cursor: default;
    transition: transform 0.35s ease, box-shadow 0.35s ease;
}}
.avatar-ring:hover {{
    transform: scale(1.06) translateY(-6px);
    box-shadow: 0 0 30px rgba(74,122,255,0.4),
                0 15px 40px rgba(0,0,0,0.6);
}}
.greet-main {{ font-size: 42px; font-weight: 800; color: #fff; letter-spacing: -0.03em; line-height: 1.1; margin-bottom: 8px; }}
.greet-sub  {{ font-size: 28px; font-weight: 600; color: #bbb; letter-spacing: -0.02em; margin-bottom: 10px; }}
.greet-desc {{ font-size: 16px; color: #555; margin-bottom: 0; }}

/* ═══ Suggestion buttons ═══ */
#sug-wrap {{
    width: 100%; max-width: 820px; margin: 28px auto 0;
    padding: 0 8px;
}}
/* Force grid layout inside the Gradio Row container */
#sug-wrap > div {{
    display: grid !important;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)) !important;
    gap: 16px !important;
    width: 100% !important;
}}
#sug-wrap button {{
    background: #161616 !important;
    border: 1.5px solid #222 !important;
    border-radius: 14px !important;
    padding: 20px 16px !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    color: #bbb !important;
    text-align: center !important;
    line-height: 1.5 !important;
    min-height: 82px !important;
    cursor: pointer !important;
    transition: all 0.22s ease !important;
    width: 100% !important;
    white-space: normal !important;
    font-family: 'Inter', sans-serif !important;
}}
#sug-wrap button:hover {{
    background: #1a1a2e !important;
    border-color: #4a7aff !important;
    color: #fff !important;
    box-shadow: 0 0 24px rgba(74,122,255,0.2), 0 6px 20px rgba(0,0,0,0.35) !important;
    transform: translateY(-3px) !important;
}}

/* ═══ Chatbot ═══ */
#shavira-chatbot {{
    background: #0d0d0d !important;
    border: none !important;
    flex: 1 !important;
    min-height: 400px !important;
}}
#shavira-chatbot .message-wrap {{
    max-width: 840px !important;
    margin: 0 auto !important;
    padding: 24px 24px !important;
}}
/* User bubble */
#shavira-chatbot .message.user > div,
#shavira-chatbot [data-testid="user"] > div {{
    background: #2a2a2e !important;
    color: #f1f1f1 !important;
    border-radius: 20px !important;
    padding: 12px 20px !important;
    font-size: 15px !important;
    line-height: 1.65 !important;
    max-width: 80% !important;
    width: fit-content !important;
    box-shadow: none !important;
    border: none !important;
    margin-left: auto !important;
    z-index: 10 !important;
}}
/* Bot bubble */
#shavira-chatbot .message.bot > div,
#shavira-chatbot [data-testid="bot"] > div {{
    background: transparent !important;
    border: none !important;
    color: #e2e2e2 !important;
    border-radius: 0 !important;
    padding: 8px 0px !important;
    font-size: 15px !important;
    line-height: 1.65 !important;
    max-width: 100% !important;
    width: 100% !important;
    z-index: 10 !important;
}}
/* User avatar */
#shavira-chatbot .message.user .avatar-container img,
#shavira-chatbot [data-testid="user"] .avatar-container img {{
    background: #3a3a40 !important;
    padding: 6px !important;
    border-radius: 50% !important;
}}
/* Bot avatar */
#shavira-chatbot .avatar-container img {{
    width: 44px !important; height: 44px !important;
    border-radius: 50% !important; object-fit: cover !important;
    border: 2.5px solid #4a7aff !important;
    box-shadow: 0 0 14px rgba(74,122,255,0.3) !important;
    z-index: 12 !important;
}}

/* ═══ Input row ═══ */
#chat-input-row {{
    background: #0d0d0d !important;
    border-top: 1px solid #1a1a1a !important;
    padding: 14px 24px !important;
    position: sticky !important;
    bottom: 0 !important;
    z-index: 1000 !important;
}}
#msg-box textarea {{
    background: #181818 !important;
    border: 2px solid #252525 !important;
    border-radius: 16px !important;
    color: #e2e2e2 !important;
    font-size: 15px !important;
    padding: 16px 20px !important;
    min-height: 56px !important;
    font-family: 'Inter', sans-serif !important;
    resize: none !important;
    transition: border-color 0.2s, box-shadow 0.2s !important;
}}
#msg-box textarea:focus {{
    border-color: #4a7aff !important;
    box-shadow: 0 0 0 4px rgba(74,122,255,0.12) !important;
    outline: none !important;
}}
#send-btn {{
    background: #4a7aff !important;
    border: none !important;
    border-radius: 14px !important;
    color: #fff !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    min-width: 90px !important;
    transition: all 0.18s !important;
}}
#send-btn:hover {{
    background: #3a6aef !important;
    box-shadow: 0 0 20px rgba(74,122,255,0.4) !important;
    transform: translateY(-1px) !important;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: #111; }}
::-webkit-scrollbar-thumb {{ background: #252525; border-radius: 3px; }}
"""

# ── Build UI ───────────────────────────────────────────────────────────────────
with gr.Blocks(title="SHAVIRA – Undiksha Virtual Assistant", fill_height=True) as demo:

    # ── Header ────────────────────────────────────────────────────────────────
    gr.HTML("""
    <div id="shavira-header">
        <div></div>
        <div class="center">
            <div class="logo">🎓</div>
            <span class="title">Undiksha Virtual Assistant (SHAVIRA)</span>
        </div>
        <div class="right">
            <div class="user-info">
                <div class="name">17_Ketut Bintang Galang Putra</div>
                <div class="email">bintang.galang@student.undiksha.ac.id</div>
            </div>
            <div class="user-badge">G</div>
        </div>
    </div>
    """)

    # ── Welcome + Avatar ──────────────────────────────────────────────────────
    gr.HTML(f"""
    <div id="welcome-section">
        <div class="avatar-ring">{avatar_img_tag}</div>
        <div class="greet-main">Salam Harmoni!</div>
        <div class="greet-sub">Hai, saya Shavira</div>
        <div class="greet-desc">Silakan tanyakan apapun tentang Undiksha :-)</div>
    </div>
    """)

    # ── Suggestion buttons ────────────────────────────────────────────────────
    with gr.Row(elem_id="sug-wrap"):
        sug_btns = []
        for sug in SUGGESTIONS:
            btn = gr.Button(sug, size="lg")
            sug_btns.append(btn)

    # ── Chatbot ───────────────────────────────────────────────────────────────
    chatbot = gr.Chatbot(
        elem_id="shavira-chatbot",
        avatar_images=(
            user_avatar_uri,
            avatar_path if os.path.exists(avatar_path) else None,
        ),
        show_label=False,
        render_markdown=True,
        scale=1,
    )

    # ── Input row ─────────────────────────────────────────────────────────────
    with gr.Row(elem_id="chat-input-row"):
        msg_box = gr.Textbox(
            placeholder="Tanyakan sesuatu tentang Undiksha...",
            show_label=False,
            elem_id="msg-box",
            scale=8,
            autofocus=True,
            lines=1,
            max_lines=4,
        )
        send_btn = gr.Button("Kirim ➤", elem_id="send-btn", scale=1, variant="primary")

    # ── Event handlers ────────────────────────────────────────────────────────
    def handle_send(message, history):
        return respond(message, history)

    msg_box.submit(handle_send, [msg_box, chatbot], [chatbot, msg_box])
    send_btn.click(handle_send, [msg_box, chatbot], [chatbot, msg_box])

    # Suggestion buttons wire
    def make_sug_handler(text):
        def handler(history):
            return respond(text, history)
        return handler

    for i, btn in enumerate(sug_btns):
        btn.click(make_sug_handler(SUGGESTIONS[i]), [chatbot], [chatbot, msg_box])

# ── Launch ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\nSHAVIRA berjalan di: http://localhost:7861\n")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=False,
        favicon_path=avatar_path if os.path.exists(avatar_path) else None,
        css=CSS,
        theme=gr.themes.Base(primary_hue=gr.themes.colors.blue, neutral_hue=gr.themes.colors.neutral)
    )
