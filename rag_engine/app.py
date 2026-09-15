"""
SHAVIRA – FastAPI + HTML/CSS/JS app
Run: python app.py
"""
import os
import sys
import base64

# Force offline mode — gunakan model cache lokal tanpa cek internet
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# ── Setup ─────────────────────────────────────────────────────────────────────
root_path = os.path.abspath(os.path.dirname(__file__))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

load_dotenv()

from src.crag.workflow import CRAGWorkflow
from src.retrieval.retriever import Retriever
from src.generation.generator import Generator

# ── Init RAG ──────────────────────────────────────────────────────────────────
db_path = os.path.join(root_path, "storage", "faiss_db")
retriever = Retriever(db_path=db_path)
crag = CRAGWorkflow(model_name="gpt-4o-mini")
generator = Generator(model_name="gpt-4o-mini")

# ── Avatar ────────────────────────────────────────────────────────────────────
avatar_path = os.path.join(root_path, "assets", "shavira_avatar.png")
try:
    with open(avatar_path, "rb") as f:
        avatar_b64 = base64.b64encode(f.read()).decode()
    avatar_src = f"data:image/png;base64,{avatar_b64}"
except Exception:
    avatar_src = ""

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI()

class ChatRequest(BaseModel):
    message: str
    mode: str = "crag"  # "naive" atau "crag"

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    query = req.message.strip()
    mode = getattr(req, "mode", "crag")
    if not query:
        return JSONResponse({"answer": "", "sources": []})

    if mode == "naive":
        # 1a. Retrieval (Naive RAG, basic Semantic Search Top-3)
        nodes = retriever.search_naive(query)
        if not nodes:
            return JSONResponse({
                "answer": "Maaf, saya tidak menemukan informasi tersebut dalam dokumen saya.",
                "sources": []
            })
        # Build raw string context
        context_list = []
        for node in nodes:
            content = node.get_content()
            source = node.metadata.get('file_name', 'Unknown')
            page = node.metadata.get('page_label', '-')
            context_list.append(f"[Sumber: {source}, Hal: {page}]\nIsi: {content}")
        combined_context = "\n\n".join(context_list)
        
    else:
        # 1b. Retrieval (Top-20 -> Cross-Encoder Top-5)
        nodes = retriever.search(query)
        if not nodes:
            # Fallback langsung web search jika database internal sama sekali tidak punya kecocokan awal
            process_logs = []
            combined_context = crag._web_search(query)
            if not combined_context:
                return JSONResponse({
                    "answer": "Maaf, saya tidak menemukan informasi tersebut dalam dokumen maupun web.",
                    "sources": []
                })
        else:
            # 2. CRAG Workflow (Evaluator -> Refinement / Rewrite -> Web Search -> Combine)
            combined_context, process_logs = crag.run(query, nodes)

    # 3. Generation
    response = generator.generate(query, combined_context)
    
    # 4. Extract Sources for UI
    sources = []
    
    # Map score from process_logs
    log_map = {}
    if mode != "naive":
        for log in process_logs:
            log_map[log['id']] = log['score']
            
    for node in nodes:
        f_name = node.metadata.get("file_name", "Unknown")
        p_label = node.metadata.get("page_label", "-")
        score = log_map.get(node.node_id, "")
        
        sources.append({
            "file": f_name,
            "page": p_label,
            "score": score
        })
        
    if mode == "crag" and "Web:" in combined_context:
         sources.append({
            "file": "External Web Search (undiksha.ac.id)",
            "page": "-",
            "score": "Web Search Triggered"
        })

    return JSONResponse({"answer": str(response), "sources": sources})

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=get_html(), status_code=200)

def get_html():
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SHAVIRA – Undiksha Virtual Assistant</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
/* ═══════════════════════════════ RESET ═══════════════════════════════ */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html,body{{height:100%;background:#0d0d0d;color:#e2e2e2;font-family:'Inter',sans-serif;overflow:hidden}}

/* ═══════════════════════════════ LAYOUT ═══════════════════════════════ */
#app{{display:flex;height:100vh;width:100vw;overflow:hidden}}

/* ═══════════════════════════════ SIDEBAR ═══════════════════════════════ */
#sidebar{{
    width:230px;min-width:230px;
    background:#111;
    border-right:1px solid #1e1e1e;
    display:flex;flex-direction:column;
    position:relative;
    flex-shrink:0;
}}
.nav-brand{{
    padding:22px 20px 16px;
    font-size:19px;font-weight:800;color:#fff;
    display:flex;align-items:center;gap:10px;
    border-bottom:1px solid #1e1e1e;
    letter-spacing:-0.02em;
}}
.nav-btn{{
    margin:12px 12px 4px;
    background:#1c1c1c;
    border:1px solid #282828;
    border-radius:10px;
    padding:11px 16px;
    color:#aaa;font-size:14px;font-weight:500;
    cursor:pointer;text-align:left;
    transition:all 0.18s;width:calc(100% - 24px);
    font-family:'Inter',sans-serif;
}}
.nav-btn:hover{{background:#252535;border-color:#4a7aff;color:#fff}}
.nav-item{{
    padding:12px 20px;font-size:14px;color:#777;
    display:flex;align-items:center;gap:10px;
    border-radius:10px;margin:2px 10px;
    cursor:pointer;transition:background 0.18s,color 0.18s;
}}
.nav-item:hover{{background:#1c1c1c;color:#ddd}}
.nav-item.active{{background:#1a1a2e;color:#7fa5ff;font-weight:600}}
.nav-item.green{{color:#34d399}}
.nav-item.red{{color:#f87171}}
.nav-footer{{
    position:absolute;bottom:20px;left:20px;
    font-size:11px;color:#333;line-height:1.9;
}}
.nav-footer strong{{color:#555;display:block}}

/* ═══════════════════════════════ MAIN ═══════════════════════════════ */
#main{{flex:1;display:flex;flex-direction:column;overflow:hidden;background:#0d0d0d}}

/* ═══════════════════════════════ HEADER ═══════════════════════════════ */
#header{{
    height:62px;min-height:62px;
    background:#111;border-bottom:1px solid #1e1e1e;
    display:flex;align-items:center;justify-content:space-between;
    padding:0 28px;flex-shrink:0;position:relative;
}}
.header-center{{
    position:absolute;left:50%;transform:translateX(-50%);
    display:flex;align-items:center;gap:12px;
}}
.header-logo{{
    width:38px;height:38px;border-radius:50%;
    background:#1e3a8a;display:flex;align-items:center;
    justify-content:center;font-size:20px;flex-shrink:0;
}}
.header-title{{font-size:16px;font-weight:700;color:#f0f0f0;letter-spacing:-0.02em;white-space:nowrap}}
.header-right{{display:flex;align-items:center;gap:12px;margin-left:auto}}
.user-info{{text-align:right}}
.user-name{{font-size:13px;font-weight:600;color:#f0f0f0}}
.user-email{{font-size:11px;color:#555}}
.user-badge{{
    width:40px;height:40px;border-radius:50%;
    background:linear-gradient(135deg,#d97706,#f59e0b);
    display:flex;align-items:center;justify-content:center;
    font-weight:800;font-size:17px;color:#fff;
    box-shadow:0 0 0 3px rgba(217,119,6,0.25);
    flex-shrink:0;
}}

/* ═══════════════════════════════ CONTENT ═══════════════════════════════ */
#content{{flex:1;overflow-y:auto;display:flex;flex-direction:column}}
#content::-webkit-scrollbar{{width:5px}}
#content::-webkit-scrollbar-track{{background:#111}}
#content::-webkit-scrollbar-thumb{{background:#252525;border-radius:3px}}

/* ═══════════════════════════════ WELCOME ═══════════════════════════════ */
#welcome{{
    flex:1;display:flex;flex-direction:column;
    align-items:center;justify-content:center;
    padding:40px 24px 0;text-align:center;
    gap:0;
}}
.avatar-ring{{
    width:200px;height:200px;border-radius:50%;
    border:5px solid #4a7aff;overflow:hidden;
    box-shadow:0 0 0 14px rgba(74,122,255,0.07),0 0 70px rgba(74,122,255,0.4),0 24px 80px rgba(0,0,0,0.5);
    margin-bottom:28px;cursor:default;
    transition:transform 0.35s ease,box-shadow 0.35s ease;
}}
.avatar-ring:hover{{
    transform:scale(1.06) translateY(-6px);
    box-shadow:0 0 0 16px rgba(74,122,255,0.1),0 0 90px rgba(74,122,255,0.5),0 32px 100px rgba(0,0,0,0.6);
}}
.avatar-ring img{{width:100%;height:100%;object-fit:cover;display:block}}
.avatar-emoji{{font-size:80px;line-height:200px}}
.greet-main{{font-size:42px;font-weight:800;color:#fff;letter-spacing:-0.03em;line-height:1.1;margin-bottom:8px}}
.greet-sub{{font-size:28px;font-weight:600;color:#bbb;letter-spacing:-0.02em;margin-bottom:12px}}
.greet-desc{{font-size:16px;color:#555;margin-bottom:36px}}

/* ═══════════════════════════════ SUGGESTIONS ═══════════════════════════════ */
#suggestions{{
    display:grid;grid-template-columns:repeat(3,1fr);
    gap:14px;width:100%;max-width:820px;
    padding:0 0 32px;
}}
.sug-btn{{
    background:#161616;border:1.5px solid #222;border-radius:14px;
    padding:20px 16px;font-size:15px;font-weight:500;color:#bbb;
    text-align:center;line-height:1.5;min-height:82px;
    cursor:pointer;transition:all 0.22s ease;
    font-family:'Inter',sans-serif;
    display:flex;align-items:center;justify-content:center;
}}
.sug-btn:hover{{
    background:#1a1a2e;border-color:#4a7aff;color:#fff;
    box-shadow:0 0 24px rgba(74,122,255,0.2),0 6px 20px rgba(0,0,0,0.35);
    transform:translateY(-3px);
}}
.sug-btn:active{{transform:translateY(-1px)}}

/* ═══════════════════════════════ CHAT ═══════════════════════════════ */
#chat-messages{{
    flex:1;
    max-width:860px;width:100%;
    margin:0 auto;
    padding:28px 24px 0;
    display:flex;flex-direction:column;gap:20px;
}}
.msg-row-user{{display:flex;justify-content:flex-end}}
.msg-row-bot{{display:flex;justify-content:flex-start;align-items:flex-start;gap:12px}}
.bubble-user{{
    background:linear-gradient(135deg,#1d4ed8,#3b82f6);
    color:#fff;border-radius:20px 20px 4px 20px;
    padding:14px 20px;max-width:70%;font-size:15px;line-height:1.65;
    box-shadow:0 4px 20px rgba(29,78,216,0.35);
    word-wrap:break-word;white-space:pre-wrap;
}}
.bubble-bot{{
    background:#161616;border:1px solid #222;color:#e2e2e2;
    border-radius:4px 20px 20px 20px;
    padding:14px 20px;max-width:70%;font-size:15px;line-height:1.65;
    word-wrap:break-word;white-space:pre-wrap;
}}
.bot-icon{{
    width:44px;height:44px;border-radius:50%;overflow:hidden;flex-shrink:0;
    border:2.5px solid #4a7aff;box-shadow:0 0 14px rgba(74,122,255,0.3);
}}
.bot-icon img{{width:100%;height:100%;object-fit:cover}}
.sources-toggle{{
    font-size:12px;color:#4a7aff;cursor:pointer;margin-top:8px;
    display:inline-block;transition:color 0.18s;
}}
.sources-toggle:hover{{color:#7fa5ff}}
.sources-box{{
    background:#111;border:1px solid #1e1e1e;border-radius:10px;
    padding:12px 16px;margin-top:8px;font-size:12px;color:#666;
    display:none;line-height:1.8;
}}
.sources-box.open{{display:block}}

/* ═══════════════════════════════ TYPING ═══════════════════════════════ */
.typing-dot{{
    display:inline-block;width:8px;height:8px;
    border-radius:50%;background:#4a7aff;
    animation:bounce 1.2s infinite;margin:0 2px;
}}
.typing-dot:nth-child(2){{animation-delay:0.2s}}
.typing-dot:nth-child(3){{animation-delay:0.4s}}
@keyframes bounce{{0%,60%,100%{{transform:translateY(0)}}30%{{transform:translateY(-8px)}}}}

/* ═══════════════════════════════ INPUT BAR ═══════════════════════════════ */
#input-bar{{
    background:#0d0d0d;border-top:1px solid #1a1a1a;
    padding:16px 24px;flex-shrink:0;
    display:flex;align-items:center;gap:12px;
    max-width:860px;width:100%;margin:0 auto;
    box-sizing:border-box;
    /* Ensure full width within parent */
    align-self:stretch;
}}
#input-wrapper{{
    flex:1;display:flex;align-items:center;
    background:#161616;border:2px solid #252525;border-radius:16px;
    padding:4px 4px 4px 18px;gap:8px;
    transition:border-color 0.2s,box-shadow 0.2s;
}}
#input-wrapper:focus-within{{
    border-color:#4a7aff;
    box-shadow:0 0 0 4px rgba(74,122,255,0.12);
}}
#msg-input{{
    flex:1;background:transparent;border:none;outline:none;
    color:#e2e2e2;font-size:15px;font-family:'Inter',sans-serif;
    padding:12px 0;resize:none;min-height:26px;max-height:120px;
    line-height:1.5;
}}
#msg-input::placeholder{{color:#444}}
#send-btn{{
    width:44px;height:44px;border-radius:12px;flex-shrink:0;
    background:#4a7aff;border:none;color:#fff;font-size:18px;
    cursor:pointer;display:flex;align-items:center;justify-content:center;
    transition:all 0.18s;
}}
#send-btn:hover{{background:#3a6aef;box-shadow:0 0 20px rgba(74,122,255,0.4);transform:scale(1.05)}}
#send-btn:active{{transform:scale(0.97)}}
/* Bottom wrapper to hold input-bar full width */
#bottom-bar{{
    background:#0d0d0d;border-top:1px solid #1a1a1a;
    padding:16px 24px;flex-shrink:0;
    display:flex;justify-content:center;
}}
</style>
</head>
<body>
<div id="app">

  <!-- SIDEBAR -->
  <div id="sidebar">
    <div class="nav-brand">🤖 Shavira</div>
    <button class="nav-btn" onclick="newChat()">＋&nbsp;&nbsp;Chat Baru</button>
    <div class="nav-item active">💬&nbsp;&nbsp;Layar Chat</div>
    <div class="nav-item">ℹ️&nbsp;&nbsp;About&nbsp;&nbsp;˅</div>
    <div class="nav-item green">📋&nbsp;&nbsp;Feedback</div>
    <div class="nav-item red">↩&nbsp;&nbsp;Keluar</div>
    <div class="nav-footer">
      <strong>SHAVIRA</strong>
      RG-Generative AI &amp; UPA TIK<br>
      Undiksha<br>
      resika@undiksha.ac.id
    </div>
  </div>

  <!-- MAIN -->
  <div id="main">

    <!-- HEADER -->
    <div id="header">
      <div></div>
      <div class="header-center">
        <div class="header-logo">🎓</div>
        <span class="header-title">Undiksha Virtual Assistant (SHAVIRA)</span>
      </div>
      <div class="header-right">
        <button id="mode-toggle" class="nav-btn" style="margin:0; width:auto; border-color:#4a7aff; color:#7fa5ff;" onclick="toggleMode()">Mode: CRAG</button>
      </div>
    </div>

    <!-- CONTENT -->
    <div id="content">

      <!-- WELCOME (shown when no chat) -->
      <div id="welcome">
        <div class="avatar-ring">
          {"<img src='" + avatar_src + "' alt='Shavira'/>" if avatar_src else "<div class='avatar-emoji'>🤖</div>"}
        </div>
        <div class="greet-main">Salam Harmoni!</div>
        <div class="greet-sub">Hai, saya Shavira</div>
        <div class="greet-desc">Silakan tanyakan apapun tentang Undiksha :-)</div>
        <div id="suggestions">
          <button class="sug-btn" onclick="sendSuggestion(this)">Apa Makna Salam Harmoni!</button>
          <button class="sug-btn" onclick="sendSuggestion(this)">Kapan Pengumuman SNBT?</button>
          <button class="sug-btn" onclick="sendSuggestion(this)">Apa saja jalur SMBJM 2026?</button>
          <button class="sug-btn" onclick="sendSuggestion(this)">Kapan Jadwal UAS?</button>
          <button class="sug-btn" onclick="sendSuggestion(this)">Bagaimana prosedur cuti akademik?</button>
          <button class="sug-btn" onclick="sendSuggestion(this)">Apa saja informasi yang dikecualikan?</button>
        </div>
      </div>

      <!-- CHAT MESSAGES (hidden initially) -->
      <div id="chat-messages" style="display:none"></div>

    </div><!-- /content -->

    <!-- INPUT BAR -->
    <div id="bottom-bar">
      <div id="input-bar">
        <div id="input-wrapper">
          <textarea id="msg-input" rows="1"
            placeholder="Tanyakan sesuatu tentang Undiksha..."></textarea>
          <button id="send-btn" onclick="sendMessage()" title="Kirim">➤</button>
        </div>
      </div>
    </div>

  </div><!-- /main -->
</div><!-- /app -->

<script>
const AVATAR_SRC = `{avatar_src}`;
let currentMode = "crag";

function toggleMode() {{
  currentMode = currentMode === "crag" ? "naive" : "crag";
  const btn = document.getElementById("mode-toggle");
  if (currentMode === "crag") {{
      btn.textContent = "Mode: CRAG";
      btn.style.borderColor = "#4a7aff";
      btn.style.color = "#7fa5ff";
  }} else {{
      btn.textContent = "Mode: Naive RAG";
      btn.style.borderColor = "#282828";
      btn.style.color = "#aaa";
  }}
}}

function autoResize(el) {{
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}}

document.getElementById('msg-input').addEventListener('input', function() {{
  autoResize(this);
}});
document.getElementById('msg-input').addEventListener('keydown', function(e) {{
  if (e.key === 'Enter' && !e.shiftKey) {{
    e.preventDefault();
    sendMessage();
  }}
}});

function newChat() {{
  document.getElementById('chat-messages').innerHTML = '';
  document.getElementById('chat-messages').style.display = 'none';
  document.getElementById('welcome').style.display = 'flex';
  document.getElementById('msg-input').value = '';
  document.getElementById('msg-input').style.height = 'auto';
}}

function sendSuggestion(btn) {{
  const text = btn.textContent.trim();
  document.getElementById('msg-input').value = text;
  sendMessage();
}}

async function sendMessage() {{
  const input = document.getElementById('msg-input');
  const message = input.value.trim();
  if (!message) return;

  // Switch to chat view
  document.getElementById('welcome').style.display = 'none';
  const chatEl = document.getElementById('chat-messages');
  chatEl.style.display = 'flex';

  // Append user bubble
  appendBubble('user', message);
  input.value = '';
  input.style.height = 'auto';

  // Typing indicator
  const typingId = appendTyping();

  try {{
    const res = await fetch('/api/chat', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{message: message, mode: currentMode}})
    }});
    const data = await res.json();
    removeTyping(typingId);
    appendBubble('bot', data.answer, data.sources);
  }} catch(e) {{
    removeTyping(typingId);
    appendBubble('bot', '⚠️ Terjadi kesalahan koneksi. Coba lagi.');
  }}

  // Scroll to bottom
  const content = document.getElementById('content');
  content.scrollTop = content.scrollHeight;
}}

let typingCounter = 0;

function appendTyping() {{
  const chatEl = document.getElementById('chat-messages');
  const id = 'typing-' + (++typingCounter);
  const iconHtml = AVATAR_SRC
    ? `<div class="bot-icon"><img src="${{AVATAR_SRC}}" alt="Shavira"/></div>`
    : `<div class="bot-icon" style="display:flex;align-items:center;justify-content:center;font-size:20px;background:#1c1c1c">🤖</div>`;

  chatEl.insertAdjacentHTML('beforeend', `
    <div class="msg-row-bot" id="${{id}}">
      ${{iconHtml}}
      <div class="bubble-bot" style="padding:16px 20px">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    </div>
  `);
  const content = document.getElementById('content');
  content.scrollTop = content.scrollHeight;
  return id;
}}

function removeTyping(id) {{
  const el = document.getElementById(id);
  if (el) el.remove();
}}

function appendBubble(role, text, sources) {{
  const chatEl = document.getElementById('chat-messages');
  const escaped = text.replace(/</g,'&lt;').replace(/>/g,'&gt;');

  if (role === 'user') {{
    chatEl.insertAdjacentHTML('beforeend', `
      <div class="msg-row-user">
        <div class="bubble-user">${{escaped}}</div>
      </div>
    `);
  }} else {{
    const srcId = 'src-' + Date.now();
    const iconHtml = AVATAR_SRC
      ? `<div class="bot-icon"><img src="${{AVATAR_SRC}}" alt="Shavira"/></div>`
      : `<div class="bot-icon" style="display:flex;align-items:center;justify-content:center;font-size:20px;background:#1c1c1c">🤖</div>`;

    let srcHtml = '';
    if (sources && sources.length > 0) {{
      const srcList = sources.map((s,i) => {{
        let scoreBadge = '';
        if (s.score) {{
           let color = s.score === 'Correct' ? '#34d399' : (s.score === 'Incorrect' ? '#f87171' : '#fbbf24');
           if(s.score.includes('Web Search')) color = '#60a5fa';
           scoreBadge = ` <span style="color:${{color}}; font-size:10px; border:1px solid ${{color}}; padding:1px 4px; border-radius:4px; margin-left:6px;">${{s.score}}</span>`;
        }}
        return `<div><strong>[${{i+1}}]</strong> ${{s.file}} — Hal. ${{s.page}}${{scoreBadge}}</div>`
      }}).join('');
      srcHtml = `
        <div class="sources-toggle" onclick="toggleSrc('${{srcId}}')">📄 Lihat Sumber Referensi ▸</div>
        <div class="sources-box" id="${{srcId}}">${{srcList}}</div>
      `;
    }}

    chatEl.insertAdjacentHTML('beforeend', `
      <div class="msg-row-bot">
        ${{iconHtml}}
        <div style="display:flex;flex-direction:column;max-width:70%">
          <div class="bubble-bot">${{escaped}}</div>
          ${{srcHtml}}
        </div>
      </div>
    `);
  }}

  const content = document.getElementById('content');
  content.scrollTop = content.scrollHeight;
}}

function toggleSrc(id) {{
  const el = document.getElementById(id);
  const toggle = el.previousElementSibling;
  el.classList.toggle('open');
  toggle.textContent = el.classList.contains('open')
    ? '📄 Sembunyikan Sumber ▾'
    : '📄 Lihat Sumber Referensi ▸';
}}
</script>
</body>
</html>"""

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n[START] SHAVIRA berjalan di: http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
