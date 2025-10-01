
import os, re, time, random, requests, pandas as pd, streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import tldextract
from dotenv import load_dotenv

st.set_page_config(page_title="Supplier Finder — macOS 26", layout="wide", page_icon="🧭")
load_dotenv()

# Theme toggle
if "theme" not in st.session_state:
    st.session_state["theme"] = "light"

theme = st.radio(
    "Theme",
    options=["light", "dark"],
    index=0 if st.session_state["theme"] == "light" else 1,
    horizontal=True,
)

st.session_state["theme"] = theme
is_dark = (theme == "dark")

css = f"""
<style>
:root {{
  --bg: {'#0b0c0f' if is_dark else '#f6f7fb'};
  --panel: {'rgba(255,255,255,0.06)' if is_dark else '#ffffff'};
  --border: {'rgba(255,255,255,0.12)' if is_dark else '#e6e8ef'};
  --text: {'#E6E7EB' if is_dark else '#121417'};
  --muted: {'#A7AAB2' if is_dark else '#5b606b'};
  --accent: #0a84ff;
}}
html, body, [data-testid="stAppViewContainer"]{{
  background: {('radial-gradient(1000px 800px at 10% -10%, #1b1e25 0%, #0b0c0f 60%), radial-gradient(1200px 1000px at 110% 10%, #10131a 0%, #0b0c0f 60%)'
                if is_dark else '#f6f7fb')};
  color: var(--text);
  font-family: -apple-system, "SF Pro Text", Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
}}
.main .block-container{{ max-width: 1280px; padding-top: .5rem; }}
.macos-window {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 6px 22px rgba(0,0,0,{0.35 if is_dark else 0.08});
  backdrop-filter: blur(14px) saturate(120%);
}}
.window-header {{ display:flex; align-items:center; gap:10px; padding: 10px 14px; border-bottom: 1px solid var(--border); border-radius: 16px 16px 0 0; }}
.dot{{width:12px; height:12px; border-radius:999px; box-shadow: 0 0 0 1px rgba(0,0,0,0.25) inset;}}
.dot.red{{background:#ff5f57;}} .dot.yellow{{background:#febc2e;}} .dot.green{{background:#28c840;}}
.window-body{{ padding: 14px; }}
.toolbar{{ display:flex; gap:12px; flex-wrap:wrap; align-items:center;
  border:1px solid var(--border); border-radius:12px; padding:10px 12px; background: {('rgba(255,255,255,0.03)' if is_dark else '#fafbff')};}}
.table-wrapper{{ border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
@media (max-width: 900px){{ .window-body{{ padding: 10px; }} }}
</style>
"""
st.markdown(css, unsafe_allow_html=True)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
REQUEST_TIMEOUT = (10, 20)
BLOCKED_HOST_FRAGS = (
    "google.", "startpage.", "duckduckgo.", "bing.", "yahoo.", "yandex.",
    "facebook.", "instagram.", "twitter.", "x.com", "linkedin.", "pinterest.",
    "youtube.", "tiktok.", "wikipedia.", "amazon.", "alibaba.", "aliexpress.",
    "ebay.", "etsy.", "reddit.", "quora.", "medium.", "baidu."
)
SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".zip")
CONTACT_HINTS = ("contact", "contacts", "contact-us", "kontakt", "contacto", "contato", "impressum", "about", "company",
                 "تماس", "ارتباط", "اتصال", "контакты", "о-компании")
WHATSAPP_PAT = re.compile(r"(?:https?://)?(?:wa\.me/\d+|api\.whatsapp\.com/send\?phone=\+?\d+)", re.I)
EMAIL_PAT = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_PAT = re.compile(r"(\+\d[\d \-\(\)]{6,}\d)")

GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY")
GOOGLE_CSE_CX  = os.getenv("GOOGLE_CSE_CX")

def pick_headers():
    return {"User-Agent": random.choice(USER_AGENTS), "Accept-Language": "en-US,en;q=0.8", "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

def normalized_domain(url: str) -> str:
    try:
        ext = tldextract.extract(url)
        if ext.domain and ext.suffix:
            return f"{ext.domain}.{ext.suffix}".lower()
    except Exception:
        pass
    return urlparse(url).netloc.split("@")[-1].split(":")[0].lower()

def is_good_result(href: str) -> bool:
    if not href: return False
    href = href.strip()
    if any(href.lower().endswith(ext) for ext in SKIP_EXTENSIONS): return False
    host = normalized_domain(href)
    if any(bad in host for bad in BLOCKED_HOST_FRAGS): return False
    return True

def http_get(url, **kwargs):
    try:
        r = requests.get(url, timeout=REQUEST_TIMEOUT, **kwargs); r.raise_for_status(); return r
    except Exception as e:
        st.warning(f"GET خطا: {e}"); return None

def http_post(url, **kwargs):
    try:
        r = requests.post(url, timeout=REQUEST_TIMEOUT, **kwargs); r.raise_for_status(); return r
    except Exception as e:
        st.warning(f"POST خطا: {e}"); return None

def search_ddg_html(query, start=0, per_page=20):
    base = "https://html.duckduckgo.com/html/"
    r = http_post(base, data={"q": query, "s": start}, headers=pick_headers())
    if not r: return []
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for a in soup.select("a.result__a"):
        u = a.get("href")
        if u and is_good_result(u):
            out.append(u)
            if len(out) >= per_page: break
    return out

def search_google_cse(query, start=0, per_page=20):
    if not (GOOGLE_CSE_KEY and GOOGLE_CSE_CX): return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_CSE_KEY, "cx": GOOGLE_CSE_CX, "q": query, "start": max(1, start+1), "num": min(per_page, 10)}
    r = http_get(url, params=params)
    if not r: return []
    data = r.json(); items = data.get("items", [])
    return [it.get("link") for it in items if it.get("link")]

def search_with_fallback(query, start=0, per_page=20):
    urls = search_ddg_html(query, start, per_page)
    if urls: return urls, "ddg"
    urls = search_google_cse(query, start, per_page)
    if urls: return urls, "google_cse"
    st.error("هیچ موتور جستجویی در دسترس نیست. DNS/اینترنت را چک کنید یا Google CSE را در .env تنظیم کنید.")
    return [], None

def fetch(url, allow_redirects=True):
    try:
        r = requests.get(url, headers=pick_headers(), timeout=REQUEST_TIMEOUT, allow_redirects=allow_redirects)
        if r.status_code == 200 and "text/html" in r.headers.get("Content-Type",""):
            return r.text, r.url
    except Exception:
        return None, url
    return None, url

def possible_contact_urls(base_url: str):
    urls = set([base_url])
    for hint in CONTACT_HINTS:
        urls.add(urljoin(base_url, f"/{hint}")); urls.add(urljoin(base_url, f"/{hint}/"))
    return list(urls)

def extract_contacts(html: str):
    emails = set(m.group(0) for m in EMAIL_PAT.finditer(html or ""))
    phones = set(m.group(1) for m in PHONE_PAT.finditer(html or ""))
    whatsapps = set(m.group(0) for m in WHATSAPP_PAT.finditer(html or ""))
    return list(emails), list(phones), list(whatsapps)

def crawl_contacts(site_url: str, max_pages_per_site: int = 3, pause: float = 1.0):
    visited = set()
    emails_all, phones_all, wapp_all = set(), set(), set()
    for candidate in possible_contact_urls(site_url):
        if len(visited) >= max_pages_per_site: break
        if candidate in visited: continue
        visited.add(candidate)
        html, _ = fetch(candidate)
        if not html: continue
        emails, phones, wapps = extract_contacts(html)
        emails_all.update(emails); phones_all.update(phones); wapp_all.update(wapps)
        time.sleep(pause)
    return list(emails_all), list(phones_all), list(wapp_all)

def filter_supplier_like(url: str, html: str = "") -> bool:
    host = normalized_domain(url)
    if any(b in host for b in ("amazon.", "alibaba.", "aliexpress.", "ebay.", "etsy.")):
        return False
    return True

if "query_key" not in st.session_state: st.session_state["query_key"] = ""
if "page_cursor" not in st.session_state: st.session_state["page_cursor"] = 0
if "seen_domains" not in st.session_state: st.session_state["seen_domains"] = set()
if "results_rows" not in st.session_state: st.session_state["results_rows"] = []

st.markdown('<div class="macos-window">', unsafe_allow_html=True)
st.markdown('<div class="window-header"><div style="display:flex; gap:8px; align-items:center;"><div class="dot red"></div><div class="dot yellow"></div><div class="dot green"></div></div><div style="font-weight:600; margin-left:10px;">Supplier Finder — macOS 26</div></div>', unsafe_allow_html=True)
st.markdown('<div class="window-body">', unsafe_allow_html=True)

colA, colB = st.columns([3, 2.2], gap="large")
with colA:
    st.markdown('<div class="toolbar">', unsafe_allow_html=True)
    c1, c2 = st.columns([6,1])
    with c1:
        query_input = st.text_input(" ", value="", placeholder="نام محصول + کشور هدف — مثال: Apple puree supplier Russia")
    with c2:
        st.caption("⌘K")
    st.markdown('</div>', unsafe_allow_html=True)
with colB:
    st.markdown('<div class="toolbar">', unsafe_allow_html=True)
    country_hint = st.text_input("اشاره کشور/زبان (اختیاری)", value="", placeholder="Russia / India / UAE ...")
    st.markdown('</div>', unsafe_allow_html=True)

s1, s2, s3, s4, s5 = st.columns(5)
with s1: per_page = st.slider("Links/page", 5, 30, 20, 5)
with s2: page_batch = st.slider("Pages/click", 1, 5, 2, 1)
with s3: max_sites = st.slider("Max sites", 10, 120, 60, 5)
with s4: max_pages = st.slider("Pages/site", 1, 6, 3, 1)
with s5: crawl_pause = st.slider("Delay (s)", 0.2, 3.0, 1.0, 0.1)

b1, b2, b3, b4 = st.columns([1,1,1,1])
with b1: search_btn = st.button("🔎 جستجو", use_container_width=True)
with b2: more_btn   = st.button("➕ ادامه جستجو", use_container_width=True)
with b3: reset_btn  = st.button("🔁 جستجوی تازه", use_container_width=True)
with b4: clear_btn  = st.button("❌ پاک کردن حافظه", use_container_width=True)

if clear_btn or reset_btn:
    st.session_state["page_cursor"] = 0
    st.session_state["seen_domains"] = set()
    st.session_state["results_rows"] = []
    st.success("حافظه پاک شد.")

query = (query_input or "").strip()
query_full = f"{query} {country_hint.strip()}".strip() if country_hint.strip() else query

if query_full != st.session_state["query_key"]:
    st.session_state["query_key"] = query_full
    st.session_state["page_cursor"] = 0
    st.session_state["seen_domains"] = set()
    st.session_state["results_rows"] = []

def run_search_batch(query_full, cursor, pages_per_click, per_page, seen_domains):
    start = cursor
    new_urls = []
    for _ in range(pages_per_click):
        urls, engine = search_with_fallback(query_full, start, per_page)
        if engine is None:
            break
        for u in urls:
            dom = normalized_domain(u)
            if dom and dom not in seen_domains:
                seen_domains.add(dom)
                new_urls.append(u)
        start += per_page
        time.sleep(1.0)
    return new_urls, start

if (search_btn or more_btn) and query_full:
    batch = page_batch if more_btn else max(2, page_batch)
    st.info(f"Query: **{query_full}** — Offset: {st.session_state['page_cursor']} — Pages this run: {batch}")
    new_urls, new_cursor = run_search_batch(query_full, st.session_state["page_cursor"], batch, per_page, st.session_state["seen_domains"])
    st.session_state["page_cursor"] = new_cursor
    st.markdown(f"**{len(new_urls)}** لینک جدید برای بررسی پیدا شد.")

    rows_added = 0
    for i, u in enumerate(new_urls[:max_sites], start=1):
        with st.spinner(f"[{i}/{min(len(new_urls), max_sites)}] بررسی: {u}"):
            html, final_url = fetch(u)
            final_url = final_url or u
            base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(final_url))
            if not filter_supplier_like(final_url, html or ""):
                continue
            emails, phones, wapps = crawl_contacts(base, max_pages_per_site=max_pages, pause=crawl_pause)
            st.session_state["results_rows"].append({
                "Website": base,
                "Emails": ", ".join(sorted(set(emails))) if emails else "",
                "Phones": ", ".join(sorted(set(phones))) if phones else "",
                "WhatsApp": ", ".join(sorted(set(wapps))) if wapps else "",
                "Source Page": final_url,
            })
            rows_added += 1

    if rows_added == 0:
        st.warning("مورد تازه‌ای اضافه نشد. «➕ ادامه جستجو» را بزن یا عبارت را تغییر بده.")

if st.session_state["results_rows"]:
    df = pd.DataFrame(st.session_state["results_rows"]).drop_duplicates(subset=["Website"])
    st.markdown("#### نتایج")
    st.markdown('<div class="table-wrapper">', unsafe_allow_html=True)
    st.dataframe(df, use_container_width=True, height=430)
    st.markdown('</div>', unsafe_allow_html=True)
    st.download_button("⬇️ دانلود CSV نتایج", df.to_csv(index=False).encode("utf-8"), "supplier_results.csv", "text/csv")
