"""fish.audio 로그인용 브라우저 창 (전용 프로필: audio/.fish_profile). 사용자가 로그인 후 창을 닫으면 종료."""
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROF = Path(__file__).resolve().parent / ".fish_profile"
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROF), channel="chrome", headless=False, no_viewport=True, locale="ko-KR",
        ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled", "--window-size=1300,900"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://fish.audio/", wait_until="domcontentloaded")
    t0 = time.time()
    while time.time() - t0 < 1800:
        try:
            if not ctx.pages:
                break
            ctx.pages[0].wait_for_timeout(2000)
        except Exception:
            break
    try:
        ctx.close()
    except Exception:
        pass
print("LOGIN WINDOW CLOSED")
