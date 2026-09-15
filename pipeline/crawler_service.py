"""
pipeline/crawler_service.py
Web Crawler Service — Concurrent Crawling + Robots.txt Support + Persistent URL History
"""
import os
import re
import json
import uuid
import hashlib
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlparse, urljoin, unquote
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
import pypdf
import io

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CRAWL_DIR = os.path.join(BASE_DIR, "data", "raw_crawled")
VISITED_HISTORY_FILE = os.path.join(BASE_DIR, "data", "crawl_history.json")
os.makedirs(RAW_CRAWL_DIR, exist_ok=True)

# Jumlah worker paralel saat crawling
CONCURRENT_WORKERS = 4


class UndikshaWebCrawler:
    def __init__(self, raw_dir: str = RAW_CRAWL_DIR):
        self.raw_dir = raw_dir
        os.makedirs(self.raw_dir, exist_ok=True)

        # State tracking
        self.is_running = False
        self.current_seed = ""
        self.allowed_domain = ""
        self.max_pages = 20
        self.auto_ingest = False

        self.pages_crawled = 0
        self.visited_urls: Set[str] = set()
        self.crawled_results: List[Dict[str, Any]] = []
        self.logs: List[str] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # Persistent URL history (lintas sesi)
        self._persistent_visited: Set[str] = self._load_persistent_history()

        # Robots.txt parser cache: domain -> RobotFileParser
        self._robots_cache: Dict[str, RobotFileParser] = {}

        # Semaphore untuk batasi concurrent requests
        self._semaphore: Optional[asyncio.Semaphore] = None

        # HTTP headers
        self._headers = {
            "User-Agent": "Shavira-KBMS-Crawler/2.0 (+https://undiksha.ac.id/shavira)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7"
        }

    # ===== Persistent URL History =====
    def _load_persistent_history(self) -> Set[str]:
        if os.path.exists(VISITED_HISTORY_FILE):
            try:
                with open(VISITED_HISTORY_FILE, "r") as f:
                    data = json.load(f)
                    return set(data.get("visited_urls", []))
            except Exception:
                pass
        return set()

    def _save_persistent_history(self):
        try:
            with open(VISITED_HISTORY_FILE, "w") as f:
                # Simpan maksimal 5000 URL terakhir
                urls = list(self._persistent_visited)[-5000:]
                json.dump({"visited_urls": urls, "updated_at": datetime.now().isoformat()}, f)
        except Exception as e:
            self.log(f"⚠️ Gagal menyimpan history URL: {e}")

    # ===== Logging =====
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.logs.append(entry)
        if len(self.logs) > 300:
            self.logs = self.logs[-300:]
        try:
            print(entry)
        except Exception:
            print(entry.encode("ascii", errors="replace").decode("ascii"))

    def get_status(self) -> Dict[str, Any]:
        duration = 0.0
        if self.start_time:
            duration = round((self.end_time or time.time()) - self.start_time, 2)
        return {
            "is_running": self.is_running,
            "current_seed": self.current_seed,
            "allowed_domain": self.allowed_domain,
            "max_pages": self.max_pages,
            "pages_crawled": self.pages_crawled,
            "duration_sec": duration,
            "auto_ingest": self.auto_ingest,
            "logs": self.logs[-20:],
            "total_logs_count": len(self.logs),
            "persistent_history_count": len(self._persistent_visited)
        }

    # ===== Robots.txt =====
    async def _get_robots(self, base_url: str, client: httpx.AsyncClient) -> RobotFileParser:
        """Ambil dan parse robots.txt untuk domain. Di-cache per domain."""
        parsed = urlparse(base_url)
        domain = parsed.netloc
        if domain in self._robots_cache:
            return self._robots_cache[domain]

        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        try:
            res = await client.get(robots_url, timeout=5.0)
            if res.status_code == 200:
                rp.parse(res.text.splitlines())
                self.log(f"🤖 robots.txt dimuat dari {domain}")
            else:
                rp.allow_all = True
        except Exception:
            rp.allow_all = True

        self._robots_cache[domain] = rp
        return rp

    def _can_fetch(self, robots: RobotFileParser, url: str) -> bool:
        try:
            return robots.can_fetch(self._headers["User-Agent"], url)
        except Exception:
            return True

    # ===== HTML & PDF Extraction =====
    def clean_html(self, html_content: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html_content, 'html.parser')

        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find('h1'):
            title = soup.find('h1').get_text().strip()
        else:
            title = urlparse(url).path.strip("/").replace("-", " ").title() or "Halaman Web Undiksha"

        internal_links = []
        parsed_domain = self.allowed_domain or urlparse(url).netloc
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            full_url = urljoin(url, href)
            parsed = urlparse(full_url)
            if parsed.scheme in ["http", "https"] and parsed_domain in parsed.netloc:
                if not re.search(r'\.(png|jpg|jpeg|gif|css|js|ico|zip|rar|mp4|mp3|exe|apk|xlsx?)$',
                                 parsed.path, re.I):
                    clean_link = full_url.split('#')[0]
                    if clean_link != url:
                        internal_links.append(clean_link)

        for el in soup(["script", "style", "noscript", "svg", "iframe", "nav", "footer"]):
            el.decompose()

        text = "\n".join(l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip())
        return {"title": title, "text": text, "links": list(set(internal_links))}

    def extract_pdf(self, pdf_bytes: bytes, url: str) -> Dict[str, Any]:
        try:
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            pages_text = [p.extract_text() or "" for p in reader.pages]
            full_text = "\n\n".join(pages_text).strip()
            filename = os.path.basename(urlparse(url).path) or "Dokumen_PDF.pdf"
            title = unquote(filename).replace("_", " ").replace("-", " ")
            if title.lower().endswith(".pdf"):
                title = title[:-4]
            return {"title": f"[PDF] {title.title()}", "text": full_text, "links": []}
        except Exception as e:
            self.log(f"⚠️ Gagal ekstrak PDF dari {url}: {e}")
            return {"title": "PDF Undiksha", "text": "", "links": []}

    def determine_metadata(self, url: str, title: str) -> Dict[str, str]:
        url_l, title_l = url.lower(), title.lower()
        if "jdih" in url_l or "hukum" in url_l or "peraturan" in url_l or "sk" in title_l:
            return {"category": "peraturan_kebijakan", "document_type": "peraturan", "source_unit": "JDIH Undiksha"}
        if "akademik" in url_l or "kurikulum" in url_l or "panduan" in title_l:
            return {"category": "akademik_kurikulum", "document_type": "panduan", "source_unit": "BAAK Undiksha"}
        if "kemahasiswaan" in url_l or "beasiswa" in url_l:
            return {"category": "kemahasiswaan", "document_type": "pengumuman", "source_unit": "Kemahasiswaan Undiksha"}
        if "kerjasama" in url_l or "mou" in url_l:
            return {"category": "mou_perjanjian_kerjasama", "document_type": "mou", "source_unit": "Humas & Kerjasama"}
        if "sop" in title_l or "pedoman" in title_l:
            return {"category": "pedoman_sop", "document_type": "sop", "source_unit": "LPM Undiksha"}
        return {"category": "lainnya", "document_type": "web_page", "source_unit": "Web Undiksha"}

    # ===== Core Crawl Worker =====
    async def _crawl_single(
        self,
        url: str,
        client: httpx.AsyncClient,
        robots: RobotFileParser,
        queue: asyncio.Queue,
        ingest_service=None
    ):
        """Worker untuk satu URL. Berjalan secara concurrent."""
        async with self._semaphore:
            if self.pages_crawled >= self.max_pages:
                return

            # Cek robots.txt
            if not self._can_fetch(robots, url):
                self.log(f"  🚫 Diblokir robots.txt: {url}")
                return

            self.log(f"🔍 Fetching [{self.pages_crawled + 1}/{self.max_pages}]: {url[:80]}")

            try:
                res = await client.get(url, timeout=15.0, follow_redirects=True)
                if res.status_code != 200:
                    self.log(f"  ❌ HTTP {res.status_code}: {url[:60]}")
                    return

                content_type = res.headers.get("content-type", "").lower()
                is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

                if is_pdf:
                    extracted = self.extract_pdf(res.content, url)
                else:
                    extracted = self.clean_html(res.text, url)

                title = extracted["title"]
                text = extracted["text"]
                links = extracted.get("links", [])

                if len(text.split()) < 25:
                    self.log(f"  ⚠️ Terlalu pendek ({len(text.split())} kata): {url[:60]}")
                    return

                content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
                meta = self.determine_metadata(url, title)
                page_id = f"RAW-CRAWL-{uuid.uuid4().hex[:8].upper()}"
                ts = datetime.now().isoformat()

                crawled_doc = {
                    "page_id": page_id, "title": title, "source_url": url,
                    "source_unit": meta["source_unit"], "category": meta["category"],
                    "document_type": meta["document_type"], "text": text,
                    "content_hash": content_hash, "crawled_at": ts,
                    "status": "active", "version": 1,
                    "word_count": len(text.split()), "char_count": len(text)
                }

                raw_path = os.path.join(self.raw_dir, f"{page_id}.json")
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(crawled_doc, f, ensure_ascii=False, indent=2)

                self.crawled_results.append(crawled_doc)
                self.pages_crawled += 1
                self._persistent_visited.add(url)
                self.log(f"  ✅ '{title[:50]}...' ({len(text.split())} kata)")

                # Auto-Ingest
                if self.auto_ingest and ingest_service:
                    try:
                        res_i = ingest_service.ingest_document(
                            title=title, content=text,
                            category=meta["category"], subcategory=meta["source_unit"],
                            document_type=meta["document_type"], source_url=url,
                            source_unit=meta["source_unit"], status="active", version=1,
                            topic_tags=["crawled", meta["category"], "undiksha"],
                            target_audience=["mahasiswa", "dosen", "staf", "umum"]
                        )
                        status_msg = res_i.get("status", "success")
                        if status_msg == "duplicate":
                            self.log(f"  🔁 Duplikat (skip): {title[:40]}")
                        else:
                            self.log(f"  📥 Ingested: {res_i.get('doc_id')} ({res_i.get('chunks_ingested', 0)} chunks)")
                    except Exception as ie:
                        self.log(f"  ⚠️ Auto-Ingest gagal: {ie}")

                # Tambah link baru ke queue
                for link in links:
                    if (link not in self.visited_urls
                            and link not in self._persistent_visited
                            and self.pages_crawled < self.max_pages):
                        await queue.put(link)

            except httpx.TimeoutException:
                self.log(f"  ⏱️ Timeout: {url[:60]}")
            except Exception as e:
                self.log(f"  ❌ Error: {url[:60]} — {e}")

    # ===== Main Crawl Coordinator =====
    async def crawl_site(
        self,
        seed_url: str,
        allowed_domain: Optional[str] = None,
        max_pages: int = 15,
        auto_ingest: bool = False,
        ingest_service=None
    ) -> List[Dict[str, Any]]:
        if self.is_running:
            self.log("⚠️ Crawler sudah berjalan!")
            return self.crawled_results

        self.is_running = True
        self.current_seed = seed_url
        self.max_pages = max_pages
        self.auto_ingest = auto_ingest
        self.pages_crawled = 0
        self.visited_urls.clear()
        self.crawled_results.clear()
        self.logs.clear()
        self.start_time = time.time()
        self.end_time = None
        self._semaphore = asyncio.Semaphore(CONCURRENT_WORKERS)

        parsed_seed = urlparse(seed_url)
        if not parsed_seed.scheme:
            seed_url = "https://" + seed_url
            parsed_seed = urlparse(seed_url)

        self.allowed_domain = allowed_domain or parsed_seed.netloc
        self.log(f"🚀 Crawl dimulai: {seed_url}")
        self.log(f"   Domain: {self.allowed_domain} | Max: {max_pages} halaman | Workers: {CONCURRENT_WORKERS}")

        try:
            async with httpx.AsyncClient(
                headers=self._headers,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=CONCURRENT_WORKERS + 2)
            ) as client:
                # Load robots.txt
                robots = await self._get_robots(seed_url, client)

                queue: asyncio.Queue = asyncio.Queue()
                await queue.put(seed_url)

                tasks = set()

                while (not queue.empty() or tasks) and self.pages_crawled < max_pages:
                    # Buat task baru dari queue
                    while not queue.empty() and self.pages_crawled + len(tasks) < max_pages:
                        url = await queue.get()
                        if url in self.visited_urls or url in self._persistent_visited:
                            continue
                        self.visited_urls.add(url)

                        task = asyncio.create_task(
                            self._crawl_single(url, client, robots, queue, ingest_service)
                        )
                        tasks.add(task)

                    if not tasks:
                        break

                    # Tunggu minimal satu task selesai
                    done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

                # Batalkan task yang tersisa
                for t in tasks:
                    t.cancel()
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.log(f"❌ Fatal error: {e}")
        finally:
            self.is_running = False
            self.end_time = time.time()
            self._save_persistent_history()
            duration = round(self.end_time - self.start_time, 2)
            self.log(f"🎉 Selesai! {self.pages_crawled} halaman dalam {duration}s ({CONCURRENT_WORKERS} workers paralel)")

        return self.crawled_results

    # ===== List & Detail =====
    def list_crawled_pages(self) -> List[Dict[str, Any]]:
        pages = []
        if not os.path.exists(self.raw_dir):
            return pages
        for fname in os.listdir(self.raw_dir):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.raw_dir, fname), "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    pages.append({
                        "page_id": doc.get("page_id", fname.replace(".json", "")),
                        "title": doc.get("title", "Halaman Web"),
                        "source_url": doc.get("source_url", ""),
                        "source_unit": doc.get("source_unit", "Web Undiksha"),
                        "category": doc.get("category", "lainnya"),
                        "document_type": doc.get("document_type", "web_page"),
                        "crawled_at": doc.get("crawled_at", ""),
                        "word_count": doc.get("word_count", 0),
                        "status": doc.get("status", "active"),
                        "version": doc.get("version", 1)
                    })
            except Exception:
                pass
        pages.sort(key=lambda p: p.get("crawled_at", ""), reverse=True)
        return pages

    def get_crawled_page_detail(self, page_id: str) -> Optional[Dict[str, Any]]:
        filepath = os.path.join(self.raw_dir, f"{page_id}.json")
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def clear_history(self):
        """Hapus persistent history agar URL bisa di-crawl ulang."""
        self._persistent_visited.clear()
        if os.path.exists(VISITED_HISTORY_FILE):
            os.remove(VISITED_HISTORY_FILE)
        self.log("🗑️ Persistent crawl history dihapus.")


# Singleton Instance
crawler_instance = UndikshaWebCrawler()
