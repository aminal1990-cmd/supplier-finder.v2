
# Supplier Finder — macOS 26 (v4)
- UI روشن/تیره، ریسپانسیو
- جستجوی چندمرحله‌ای با «➕ ادامه جستجو»
- ضدتکرار دامنه و حافظهٔ مخصوص هر Query
- Fallback: DuckDuckGo HTML → Google CSE (در صورت تنظیم کلید)

## نصب
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python3 -m streamlit run streamlit_app.py
```

## Google CSE (اختیاری)
فایل `.env` کنار برنامه:
```
GOOGLE_CSE_KEY=AIza...your_key...
GOOGLE_CSE_CX=your_cx_id
```

## macOS دو-کلیک
```bash
chmod +x run_app.command
```
سپس دوبار کلیک روی `run_app.command`.
