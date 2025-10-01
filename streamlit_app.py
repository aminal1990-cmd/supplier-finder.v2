
import os, re, time, json, random, datetime as dt
import requests
import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import tldextract
from dotenv import load_dotenv

st.set_page_config(page_title="Supplier Finder — macOS 26", layout="wide", page_icon="🧭")
load_dotenv()

# Theme
if "theme" not in st.session_state: st.session_state["theme"] = "light"
theme = st.radio("Theme", options=["light","dark"], index=0 if st.session_state["theme"]=="light" else 1, horizontal=True)
st.session_state["theme"] = theme
is_dark = theme == "dark"

st.markdown(f"""
<style>
:root {{
  --bg: {'#0b0c0f' if is_dark else '#f6f7fb'};
  --panel: {'rgba(255,255,255,0.06)' if is_dark else '#ffffff'};
  --border: {'rgba(255,255,255,0.12)' if is_dark else '#e6e8ef'};
  --text: {'#E6E7EB' if is_dark else '#121417'};
  --muted: {'#A7AAB2' if is_dark else '#5b606b'};
  --accent: #0a84ff;
}}
html, body, [data-testid="stAppViewContainer"]{{ background: {('radial-gradient(1000px 800px at 10% -10%, #1b1e25 0%, #0b0c0f 60%), radial-gradient(1200px 1000px at 110% 10%, #10131a 0%, #0b0c0f 60%)' if is_dark else '#f6f7fb')}; color: var(--text); font-family: -apple-system, "SF Pro Text", Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }}
.main .block-container{{ max-width:1280px; padding-top:.5rem; }}
.macos-window{{ background:var(--panel); border:1px solid var(--border); border-radius:16px; box-shadow:0 6px 22px rgba(0,0,0,{0.35 if is_dark else 0.08}); backdrop-filter: blur(14px) saturate(120%); }}
.window-header{{ display:flex; align-items:center; gap:10px; padding:10px 14px; border-bottom:1px solid var(--border); border-radius:16px 16px 0 0; }}
.dot{{ width:12px; height:12px; border-radius:999px; box-shadow:0 0 0 1px rgba(0,0,0,.25) inset; }}
.dot.red{{background:#ff5f57}} .dot.yellow{{background:#febc2e}} .dot.green{{background:#28c840}}
.window-body{{ padding:14px; }}
.toolbar{{ display:flex; gap:12px; flex-wrap:wrap; align-items:center; border:1px solid var(--border); border-radius:12px; padding:10px 12px; background:{('rgba(255,255,255,.03)' if is_dark else '#fafbff')}; }}
.table-wrapper{{ border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
.hint{{ font-size:12px; color:var(--muted); }}
</style>
""", unsafe_allow_html=True)

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]
REQUEST_TIMEOUT = (10, 20)
BLOCKED_HOST_FRAGS = ("google.","startpage.","duckduckgo.","bing.","yahoo.","yandex.","facebook.","instagram.","twitter.","x.com","linkedin.","pinterest.","youtube.","tiktok.","wikipedia.","amazon.","alibaba.","aliexpress.","ebay.","etsy.","reddit.","quora.","medium.","baidu.")
SKIP_EXTENSIONS = (".pdf",".jpg",".jpeg",".png",".gif",".webp",".svg",".doc",".docx",".ppt",".pptx",".xls",".xlsx",".zip")
CONTACT_HINTS = ("contact","contacts","contact-us","kontakt","contacto","contato","impressum","about","company","تماس","ارتباط","اتصال","контакты","о-компании")
WHATSAPP_PAT = re.compile(r"(?:https?://)?(?:wa\.me/\d+|api\.whatsapp\.com/send\?phone=\+?\d+)", re.I)
EMAIL_PAT = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_PAT = re.compile(r"(\+\d[\d \-\(\)]{6,}\d)")

GOOGLE_CSE_KEY = os.getenv("GOOGLE_CSE_KEY")
GOOGLE_CSE_CX  = os.getenv("GOOGLE_CSE_CX")

def pick_headers():
    return {"User-Agent": random.choice(USER_AGENTS), "Accept-Language":"en-US,en;q=0.8", "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

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
    r = http_post(base, data={"q":query, "s":start}, headers=pick_headers())
    if not r: return []
    soup = BeautifulSoup(r.text, "lxml")
    out = []
    for a in soup.select("a.result__a"):
        u = a.get("href")
        if u and is_good_result(u):
            out.append(u)
            if len(out) >= per_page: break
    return out

def search_google_cse_page(query, start=1, num=10):
    if start > 91: return []
    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": GOOGLE_CSE_KEY, "cx": GOOGLE_CSE_CX, "q": query, "start": start, "num": min(10, max(1, num))}
    r = http_get(url, params=params)
    if not r: return []
    data = r.json()
    items = data.get("items", [])
    return [it.get("link") for it in items if it.get("link")]

def search_with_fallback_collect(query, start_offset, per_page, engine_hint=None):
    reached_cap = False
    if engine_hint == "google_cse" or (GOOGLE_CSE_KEY and GOOGLE_CSE_CX):
        start_param = start_offset + 1
        if start_param > 91:
            return [], "google_cse", start_offset, True
        urls = search_google_cse_page(query, start=start_param, num=min(10, per_page))
        if not urls:
            urls = search_ddg_html(query, start=start_offset, per_page=per_page)
            return urls, ("ddg" if urls else "google_cse"), start_offset + per_page, start_param > 91
        return urls, "google_cse", start_offset + per_page, (start_param + per_page > 91)
    urls = search_ddg_html(query, start=start_offset, per_page=per_page)
    if urls: return urls, "ddg", start_offset + per_page, False
    start_param = start_offset + 1
    if start_param > 91:
        return [], "google_cse", start_offset, True
    urls = search_google_cse_page(query, start=start_param, num=min(10, per_page))
    return urls, ("google_cse" if urls else None), start_offset + per_page, (start_param + per_page > 91)

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
    for hint in ("contact","contacts","contact-us","kontakt","contacto","contato","impressum","about","company","تماس","ارتباط","اتصال","контакты","о-компании"):
        urls.add(urljoin(base_url, f"/{hint}")); urls.add(urljoin(base_url, f"/{hint}/"))
    return list(urls)

def extract_contacts(html: str):
    emails = set(m.group(0) for m in re.finditer(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", html or "", re.I))
    phones = set(m.group(1) for m in re.finditer(r"(\+\d[\d \-\(\)]{6,}\d)", html or ""))
    whatsapps = set(m.group(0) for m in re.finditer(r"(?:https?://)?(?:wa\.me/\d+|api\.whatsapp\.com/send\?phone=\+?\d+)", html or "", re.I))
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
    if any(b in host for b in ("amazon.","alibaba.","aliexpress.","ebay.","etsy.")):
        return False
    return True

# AutoSave/Restore
SAVE_FILE = "session_autosave.json"

def autosave_state():
    try:
        payload = {
            "when": dt.datetime.now().isoformat(),
            "query_key": st.session_state.get("query_key",""),
            "page_cursor": st.session_state.get("page_cursor",0),
            "seen_domains": sorted(list(st.session_state.get("seen_domains", set()))),
            "results_rows": st.session_state.get("results_rows", []),
            "engine_pref": st.session_state.get("engine_pref","auto"),
            "unique_domains": st.session_state.get("unique_domains", True),
            "target_results": st.session_state.get("target_results", 100),
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.warning(f"Auto-save failed: {e}")
        return False

def autorestore_state():
    if not os.path.exists(SAVE_FILE): return False
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state["query_key"] = data.get("query_key","")
        st.session_state["page_cursor"] = data.get("page_cursor",0)
        st.session_state["seen_domains"] = set(data.get("seen_domains",[]))
        st.session_state["results_rows"] = data.get("results_rows",[])
        st.session_state["engine_pref"] = data.get("engine_pref","auto")
        st.session_state["unique_domains"] = data.get("unique_domains", True)
        st.session_state["target_results"] = data.get("target_results", 100)
        return True
    except Exception as e:
        st.warning(f"Auto-restore failed: {e}")
        return False

# Session
if "query_key" not in st.session_state: st.session_state["query_key"]=""
if "page_cursor" not in st.session_state: st.session_state["page_cursor"]=0
if "seen_domains" not in st.session_state: st.session_state["seen_domains"]=set()
if "results_rows" not in st.session_state: st.session_state["results_rows"]=[]
if "engine_pref" not in st.session_state: st.session_state["engine_pref"]="auto"
if "unique_domains" not in st.session_state: st.session_state["unique_domains"]=True
if "target_results" not in st.session_state: st.session_state["target_results"]=100
if "_restored_once" not in st.session_state:
    if autorestore_state(): st.success("✅ نتایج آخرین جلسه بازیابی شد.")
    st.session_state["_restored_once"]=True

# Window
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
with s3: max_sites = st.slider("Max sites to crawl", 10, 120, 100, 5)
with s4: max_pages = st.slider("Pages/site", 1, 6, 3, 1)
with s5: crawl_pause = st.slider("Delay (s)", 0.2, 3.0, 1.0, 0.1)

with st.sidebar:
    st.subheader("تنظیمات جستجو")
    st.session_state["target_results"] = st.slider("حداکثر نتایج هدف (تا 100 - فقط CSE)", 10, 100, value=100, step=10)
    st.session_state["unique_domains"] = st.toggle("عدم تکرار دامنه (پیشنهادی)", value=True)
    st.session_state["engine_pref"] = st.selectbox("موتور ترجیحی", options=["auto","google_cse","ddg"], index=["auto","google_cse","ddg"].index(st.session_state["engine_pref"]))
    st.markdown("---")
    auto_save = st.toggle("Auto-Save روی دیسک", value=True)
    cA, cB = st.columns(2)
    if cA.button("💾 ذخیره دستی"): st.success("ذخیره شد.") if autosave_state() else st.error("ذخیره نشد.")
    if cB.button("♻️ بازیابی دستی"):
        if autorestore_state(): st.success("بازیابی شد.")
        else: st.info("فایل بازیابی پیدا نشد.")
    st.caption("CSE فقط 100 نتیجهٔ اول را می‌دهد.")

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
    if auto_save: autosave_state()

query = (query_input or "").strip()
query_full = f"{query} {country_hint.strip()}".strip() if country_hint.strip() else query

if query_full != st.session_state["query_key"]:
    st.session_state["query_key"] = query_full
    st.session_state["page_cursor"] = 0
    st.session_state["seen_domains"] = set()
    st.session_state["results_rows"] = []

def run_search(batch_pages: int):
    start = st.session_state["page_cursor"]
    new_urls, cap_hit = [], False
    for _ in range(batch_pages):
        urls, engine, next_offset, cap = search_with_fallback_collect(
            query_full, start, per_page,
            engine_hint=st.session_state["engine_pref"] if st.session_state["engine_pref"]!="auto" else None
        )
        if engine is None:
            st.error("هیچ موتور جستجویی در دسترس نیست. DNS/اینترنت یا GOOGLE_CSE_* را چک کنید.")
            break
        for u in urls:
            dom = normalized_domain(u)
            if st.session_state["unique_domains"]:
                if dom and dom in st.session_state["seen_domains"]: continue
                if dom: st.session_state["seen_domains"].add(dom)
            new_urls.append(u)
        start = next_offset
        cap_hit = cap_hit or cap
        if len(st.session_state["results_rows"]) + len(new_urls) >= st.session_state["target_results"]:
            break
        time.sleep(1.0)
    st.session_state["page_cursor"] = start
    return new_urls, cap_hit

if (search_btn or more_btn) and query_full:
    batch = page_batch if more_btn else max(2, page_batch)
    st.info(f"Query: **{query_full}** — Offset: {st.session_state['page_cursor']} — Pages this run: {batch}")
    new_urls, cap_hit = run_search(batch)
    st.markdown(f"**{len(new_urls)}** لینک جدید برای بررسی پیدا شد.")
    if cap_hit and st.session_state["engine_pref"] in ("auto","google_cse"):
        st.warning("⚠️ به سقف ۱۰۰ نتیجهٔ Google CSE رسیدیم.")
    rows_added = 0
    for i, u in enumerate(new_urls[:max_sites], start=1):
        with st.spinner(f"[{i}/{min(len(new_urls), max_sites)}] بررسی: {u}"):
            html, final_url = fetch(u); final_url = final_url or u
            base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(final_url))
            if not filter_supplier_like(final_url, html or ""): continue
            emails, phones, wapps = crawl_contacts(base, max_pages_per_site=max_pages, pause=crawl_pause)
            st.session_state["results_rows"].append({
                "Website": base,
                "Emails": ", ".join(sorted(set(emails))) if emails else "",
                "Phones": ", ".join(sorted(set(phones))) if phones else "",
                "WhatsApp": ", ".join(sorted(set(wapps))) if wapps else "",
                "Source Page": final_url,
            })
            rows_added += 1
        if len(st.session_state["results_rows"]) >= st.session_state["target_results"]:
            break
    if rows_added == 0: st.warning("مورد تازه‌ای اضافه نشد.")
    else: st.success(f"{rows_added} سایت تازه اضافه شد.")
    if auto_save: autosave_state()

if st.session_state["results_rows"]:
    df = pd.DataFrame(st.session_state["results_rows"]).drop_duplicates(subset=["Website"]) if st.session_state["unique_domains"] else pd.DataFrame(st.session_state["results_rows"])
    st.markdown("#### نتایج")
    st.markdown('<div class="table-wrapper">', unsafe_allow_html=True)
    st.dataframe(df.head(st.session_state["target_results"]), use_container_width=True, height=450)
    st.markdown('</div>', unsafe_allow_html=True)
    st.download_button("⬇️ دانلود CSV نتایج", df.head(st.session_state["target_results"]).to_csv(index=False).encode("utf-8"), "supplier_results.csv", "text/csv")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

st.caption("macOS 26 • Responsive • AutoSave • Multi-run search • CSE cap-aware (max 100) • Toggle unique domains")
