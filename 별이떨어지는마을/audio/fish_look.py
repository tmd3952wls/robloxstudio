"""전용 프로필로 페이지를 열어 스크린샷 + 보이는 글자 저장. 사용: fish_look.py <url> <out_prefix>"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROF = Path(__file__).resolve().parent / ".fish_profile"
url, out = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROF), channel="chrome", headless=True, viewport={"width": 1400, "height": 1000}, locale="ko-KR",
        ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    page.screenshot(path=out + ".png")
    Path(out + ".txt").write_text(page.inner_text("body")[:6000], encoding="utf-8")
    print(page.url)
    ctx.close()
