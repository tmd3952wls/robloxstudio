"""전용 프로필로 fish.audio TTS 페이지에서 동작 목록 실행 후 캡처.
사용: fish_do.py <actions.json> <out_prefix>
actions: [["click_text","보이스1"], ["click","css=..."], ["fill","css=...","text"], ["press","Escape"], ["wait",2000], ["shot","name"], ["dump"]]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

PROF = Path(__file__).resolve().parent / ".fish_profile"
acts = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
out = sys.argv[2]
URL = "https://fish.audio/ko/app/text-to-speech/"
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROF), channel="chrome", headless=True, viewport={"width": 1400, "height": 1000}, locale="ko-KR",
        accept_downloads=True, ignore_default_args=["--enable-automation"], args=["--disable-blink-features=AutomationControlled"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    for a in acts:
        op = a[0]
        try:
            if op == "click_text":
                loc = page.get_by_text(a[1], exact=a[2] if len(a) > 2 else True)
                loc.last.click(timeout=8000) if (len(a) > 3 and a[3] == "last") else loc.first.click(timeout=8000)
            elif op == "click":
                page.locator(a[1]).first.click(timeout=8000)
            elif op == "click_xy":
                page.mouse.click(a[1], a[2])
            elif op == "fill":
                page.locator(a[1]).first.fill(a[2], timeout=8000)
            elif op == "press":
                page.keyboard.press(a[1])
            elif op == "insert_file":
                page.keyboard.insert_text(Path(a[1]).read_text(encoding="utf-8"))
            elif op == "type":
                page.keyboard.type(a[1])
            elif op == "wait":
                page.wait_for_timeout(a[1])
            elif op == "shot":
                page.screenshot(path=f"{out}_{a[1]}.png")
            elif op == "dump":
                Path(out + ".txt").write_text(page.inner_text("body")[:8000], encoding="utf-8")
            elif op == "html":
                Path(out + ".html").write_text(page.content(), encoding="utf-8")
            elif op == "download_xy":
                with page.expect_download(timeout=60000) as d:
                    page.mouse.click(a[1], a[2])
                d.value.save_as(a[3])
                print("saved", a[3], d.value.suggested_filename)
            elif op == "download":   # 클릭하면 다운로드되는 요소
                with page.expect_download(timeout=a[3] if len(a) > 3 else 60000) as d:
                    page.locator(a[1]).first.click()
                d.value.save_as(a[2])
                print("saved", a[2])
            print("ok", a)
        except Exception as e:
            print("FAIL", a, str(e)[:200])
    page.screenshot(path=out + "_end.png")
    ctx.close()
