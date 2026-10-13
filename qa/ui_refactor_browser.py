"""Local visual acceptance of the review workspace; never invokes an AI provider."""
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "qa/artifacts/ui-refactor"

def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results = {"scope": "Local UI only; Gemini and HTTPS deployment remain unverified", "checks": []}
    with tempfile.TemporaryDirectory(prefix="parcelverify-ui-") as directory:
        env = dict(os.environ, PV_DATA_DIR=directory, PV_AI_PROVIDER="gemini")
        env.pop("GEMINI_API_KEY", None)
        env.pop("PV_AI_API_KEY", None)
        log = (OUTPUT / "server.log").open("w", encoding="utf-8")
        server = subprocess.Popen([str(ROOT / ".venv/Scripts/python.exe"), "-m", "streamlit", "run", "app.py", "--server.port=18502", "--server.headless=true", "--browser.gatherUsageStats=false"], cwd=ROOT, env=env, stdout=log, stderr=log)
        try:
            for _ in range(60):
                try:
                    if urllib.request.urlopen("http://localhost:18502/_stcore/health", timeout=1).status == 200:
                        break
                except OSError:
                    time.sleep(.5)
            with sync_playwright() as runtime:
                browser = runtime.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
                for width in (1440, 1024, 390):
                    context = browser.new_context(viewport={"width": width, "height": 1000}, accept_downloads=True)
                    page = context.new_page()
                    page.goto("http://localhost:18502")
                    page.get_by_role("heading", name="Your review overview").wait_for(timeout=60000)
                    def capture(name):
                        page.wait_for_timeout(1200)
                        page.screenshot(path=str(OUTPUT / f"{name}-{width}.png"), full_page=True)
                        overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        errors = page.get_by_test_id("stException").count() + page.get_by_test_id("stAlert").filter(has_text="could not be completed").count()
                        results["checks"].append({"view": name, "width": width, "horizontal_overflow": overflow, "errors": errors})
                        assert not overflow, (name, width, "overflow")
                        assert not errors, (name, width, "runtime error")
                    capture("overview")
                    if width == 1440:
                        results["metric_dom"] = page.get_by_test_id("stMetric").first.evaluate("e=>e.outerHTML")
                        results["card_dom"] = page.get_by_role("button",name="Review case",exact=True).first.evaluate("e=>e.parentElement.parentElement.parentElement.parentElement.outerHTML.slice(0,1800)")
                        results["caption_style"] = page.get_by_test_id("stCaptionContainer").first.evaluate("e=>({color:getComputedStyle(e).color,opacity:getComputedStyle(e).opacity,font:getComputedStyle(e).fontSize})")
                    page.get_by_role("button", name="Review case", exact=True).first.click()
                    page.get_by_role("heading", name="PV-DEMO-001", exact=True).wait_for()
                    capture("case-summary")
                    page.get_by_text("AI summary", exact=True).click()
                    page.get_by_text("AI summary is unavailable. You can still review the evidence.", exact=True).wait_for()
                    page.get_by_role("tab", name="Evidence", exact=True).click()
                    page.get_by_role("heading", name="Shipment checks", exact=True).wait_for()
                    capture("case-evidence")
                    assert page.locator("img[src^='data:image']").count() > 0
                    page.get_by_role("button", name=re.compile("Enlarge photo")).first.click()
                    page.get_by_role("dialog").wait_for()
                    page.screenshot(path=str(OUTPUT / f"photo-dialog-{width}.png"), full_page=True)
                    page.keyboard.press("Escape")
                    page.get_by_role("button", name=re.compile("Back to cases")).click()
                    page.get_by_role("heading", name="Cases", exact=True).wait_for()
                    capture("cases")
                    if width == 390:
                        page.get_by_test_id("stExpandSidebarButton").click()
                    page.get_by_test_id("stSidebar").get_by_text("Partners", exact=True).click()
                    page.get_by_role("heading", name="Partners", exact=True).wait_for()
                    if width == 390:
                        page.get_by_test_id("stSidebarCollapseButton").get_by_role("button").click()
                    capture("partners")
                    page.keyboard.press("Tab")
                    results["checks"].append({"width": width, "keyboard_focus": page.evaluate("document.activeElement.tagName"), "buttons": page.get_by_role("button", name="View partner").evaluate_all("els => els.map(e => ({height:e.getBoundingClientRect().height,color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor}))")})
                    context.close()
                browser.close()
            results["status"] = "passed"
        finally:
            subprocess.run(["taskkill", "/PID", str(server.pid), "/T", "/F"], capture_output=True)
            log.close()
            (OUTPUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results))

if __name__ == "__main__":
    main()
