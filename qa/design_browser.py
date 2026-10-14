"""Inspect actual reference-led UI in Chrome, without calling an AI provider."""
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"qa/artifacts/design-rebuild"

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={"scope":"Local UI; hosted deployment and real AI remain unverified","checks":[]}
    with tempfile.TemporaryDirectory(prefix="parcelverify-design-") as directory:
        env=dict(os.environ,PV_DATA_DIR=directory,PV_AI_PROVIDER="gemini")
        for key in ("GEMINI_API_KEY","PV_AI_API_KEY"):env.pop(key,None)
        log=(OUT/"server.log").open("w",encoding="utf-8")
        server=subprocess.Popen([str(ROOT/".venv/Scripts/python.exe"),"-m","streamlit","run","app.py","--server.port=18503","--server.headless=true"],cwd=ROOT,env=env,stdout=log,stderr=log)
        try:
            for _ in range(60):
                try:
                    if urllib.request.urlopen("http://localhost:18503/_stcore/health",timeout=1).status==200:break
                except OSError:time.sleep(.5)
            with sync_playwright() as runtime:
                browser=runtime.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe",headless=True)
                for width,height in ((1440,900),(1024,768),(390,844)):
                    context=browser.new_context(viewport={"width":width,"height":height},accept_downloads=True)
                    page=context.new_page();page.goto("http://localhost:18503")
                    page.get_by_text("Check every handoff.",exact=False).first.wait_for(timeout=60000)
                    page.get_by_role("button",name=re.compile("Review cases")).wait_for()
                    def capture(view):
                        page.wait_for_timeout(900)
                        page.screenshot(path=str(OUT/f"{view}-{width}.png"),full_page=True)
                        overflow=page.evaluate("document.documentElement.scrollWidth > innerWidth")
                        errors=page.get_by_test_id("stException").count()+page.get_by_test_id("stAlert").filter(has_text="could not be completed").count()
                        result["checks"].append({"view":view,"width":width,"height":height,"overflow":overflow,"errors":errors})
                        assert not overflow and not errors,(view,width,overflow,errors)
                    def nav(name):
                        if width<760:
                            page.get_by_role("button",name=re.compile("Menu")).first.click()
                            page.locator(".st-key-mobile-nav-"+name).get_by_role("button").click()
                            page.keyboard.press("Escape")
                        else:page.locator(".st-key-nav-"+name).get_by_role("button").click()
                    capture("home")
                    if width==1440:
                        result["rendered_styles"]={"body":page.locator(".hero-copy").evaluate("e=>({color:getComputedStyle(e).color,fontSize:getComputedStyle(e).fontSize})"),"primary":page.get_by_role("button",name=re.compile("Review cases")).evaluate("e=>({color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,height:e.getBoundingClientRect().height})")}
                    if width==1440:
                        first=page.get_by_role("button",name=re.compile("Compare weights")).first.bounding_box()
                        assert first and first["y"]+first["height"]<=900,("first actionable issue below fold",first)
                        result["first_issue_visible_without_scroll"]=True
                    if width==390:
                        actions=page.get_by_role("button",name="Find a shipment",exact=True).bounding_box()
                        photo=page.locator(".hero-photo").bounding_box()
                        assert actions["y"]<photo["y"]
                    page.get_by_role("button",name=re.compile("Compare weights")).first.click()
                    page.get_by_role("heading",name="Check a weight difference",exact=True).wait_for()
                    capture("weight-issue")
                    page.get_by_text("AI explanation is unavailable. You can still review the evidence.",exact=True).wait_for()
                    assert page.get_by_role("button",name="Explain this issue with AI",exact=True).is_disabled()
                    photo_button=page.get_by_role("button",name=re.compile("Enlarge photo")).first
                    photo_button.click();page.get_by_role("dialog").wait_for()
                    capture("evidence-photo")
                    page.keyboard.press("Escape")
                    page.get_by_role("button",name=re.compile("Back to cases")).click()
                    page.get_by_role("heading",name="Cases to review",exact=True).wait_for()
                    capture("issues")
                    if width==1440:
                        root=page.get_by_test_id("stMain")
                        root.evaluate("e=>e.scrollTop=180")
                        page.get_by_role("button",name=re.compile("Compare weights")).first.click()
                        page.get_by_role("heading",name="Check a weight difference",exact=True).wait_for()
                        page.wait_for_timeout(500)
                        saved=page.evaluate("Number(sessionStorage.getItem('pvIssueScroll'))")
                        assert root.evaluate("e=>e.scrollTop")==0
                        page.get_by_role("button",name=re.compile("Back to cases")).click()
                        page.get_by_role("heading",name="Cases to review",exact=True).wait_for()
                        page.wait_for_timeout(500)
                        restored=root.evaluate("e=>e.scrollTop")
                        assert abs(saved-restored)<3,(saved,restored)
                        result["scroll_restoration"]={"saved":saved,"restored":restored}
                    select=page.get_by_test_id("stSelectbox").filter(has=page.get_by_text("Issue type",exact=True))
                    select.get_by_role("combobox").click()
                    page.get_by_role("option",name="Data access",exact=True).click()
                    page.locator('[class*="st-key-open-"]').get_by_role('button').first.click()
                    page.get_by_role("heading",name="Related account activity",exact=True).first.wait_for()
                    capture("access-issue")
                    nav("Partners")
                    page.get_by_role("heading",name="Delivery partners",exact=True).wait_for()
                    capture("partners")
                    page.get_by_role("button",name="View partner",exact=True).first.click()
                    page.get_by_role("heading",name=re.compile("review profile")).wait_for()
                    capture("partner-profile")
                    page.keyboard.press("Tab")
                    result["checks"].append({"width":width,"keyboard_focus":page.evaluate("document.activeElement.tagName"),"button_heights":page.get_by_role("button",name="View partner",exact=True).evaluate_all("els=>els.map(e=>e.getBoundingClientRect().height)")})
                    if width==1440:
                        nav("Home")
                        page.get_by_text("A clearer path",exact=False).scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        page.screenshot(path=str(OUT/"home-process-1440.png"))
                    context.close()
                comparison=browser.new_page(viewport={"width":1800,"height":1100})
                import base64
                ref=base64.b64encode((ROOT/"reference/GREENWAY.png").read_bytes()).decode()
                app=base64.b64encode((OUT/"home-1440.png").read_bytes()).decode()
                comparison.set_content('<html><body style="margin:0;background:#EEF5F0;font-family:Segoe UI,sans-serif;padding:24px"><h1 style="font-size:24px">Composition review: reference and actual ParcelVerify Home</h1><div style="display:grid;grid-template-columns:550px 1fr;gap:24px"><div><h2>GREENWAY visual reference</h2><img style="width:100%" src="data:image/png;base64,'+ref+'"></div><div><h2>Actual running application</h2><img style="width:100%" src="data:image/png;base64,'+app+'"><p>Compare headline scale, purposeful photography, horizontal navigation, white/green contrast and grouped operational content. This is a visual review, not a user usability study.</p></div></div></body></html>')
                comparison.screenshot(path=str(OUT/"reference-comparison.png"),full_page=True)
                browser.close()
            result["status"]="passed"
        finally:
            subprocess.run(["taskkill","/PID",str(server.pid),"/T","/F"],capture_output=True)
            log.close()
            (OUT/"results.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({"status":result.get("status"),"checks":len(result["checks"])}))

if __name__=="__main__":main()
