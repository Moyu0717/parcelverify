"""Isolated synthetic UI verification. Never enables provider execution."""
import json, os, re, subprocess, tempfile, time, urllib.request, sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'qa/artifacts/review-workspace'
sys.path.insert(0,str(ROOT))
from services.access import query_shipment
from release_info import build_information

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={'scope':'Local synthetic fixtures; no AI requests or hosted verification','build':build_information(),'before_provenance':{'directory':'qa/artifacts/design-rebuild','recorded_date':'2026-10-14','commit':'69915b8865de906144478034d4ca3584859f4638','viewports':['1440x900','390x844'],'note':'Historical actual before screenshots, not a fresh current baseline'},'checks':[]}
    with tempfile.TemporaryDirectory(prefix='parcelverify-review-') as directory:
        env=dict(os.environ,PV_DATA_DIR=directory,AI_PROVIDER='disabled',AI_EXECUTION_ENABLED='false')
        for key in ('GROQ_API_KEY','GEMINI_API_KEY','PV_AI_API_KEY'):env.pop(key,None)
        with (OUT/'server.log').open('w',encoding='utf-8') as log:
            server=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),'-m','streamlit','run','app.py','--server.port=18509','--server.headless=true','--browser.gatherUsageStats=false'],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(90):
                    try:
                        if urllib.request.urlopen('http://localhost:18509/_stcore/health',timeout=1).status==200:break
                    except OSError:time.sleep(.5)
                with sync_playwright() as runtime:
                    browser=runtime.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
                    for width,height in ((1366,768),(390,844)):
                        context=browser.new_context(viewport={'width':width,'height':height})
                        known=set(Path(directory).rglob('parcelverify.db'))
                        page=context.new_page();page.goto('http://localhost:18509')
                        page.get_by_role('heading',name='Review workspace',exact=True).wait_for(timeout=60000)
                        if width==390:
                            menu=page.get_by_role('button',name=re.compile(r'\bMenu\b'))
                            menu.click()
                            page.get_by_role('button',name='Home',exact=True).last.click()
                            expect(menu).to_have_attribute('aria-expanded','false',timeout=15000)
                        def capture(name):
                            page.wait_for_timeout(800)
                            page.screenshot(path=str(OUT/f'{name}-{width}.png'),full_page=True)
                            page.screenshot(path=str(OUT/f'{name}-viewport-{width}.png'))
                            overflow=page.evaluate('document.documentElement.scrollWidth > innerWidth')
                            errors=page.get_by_test_id('stException').count()
                            result['checks'].append({'view':name,'width':width,'height':height,'overflow':overflow,'exceptions':errors})
                            assert not overflow and not errors,(name,width,overflow,errors)
                        created=set(Path(directory).rglob('parcelverify.db'))-known
                        assert len(created)==1
                        fixture_db=str(created.pop())
                        denied=query_shipment(fixture_db,{'actor_id':'ACTOR-SL-01','partner_id':'P-SAFELOG','role':'partner_user','session_id':'visual-fixture'},'PV-SHIP-002')
                        assert not denied['authorized']
                        capture('home')
                        actions=page.locator('[class*="st-key-open-"]').get_by_role('button')
                        if width==1366:
                            boxes=[actions.nth(i).bounding_box() for i in range(2)]
                            assert all(box and box['y']+box['height']<=height for box in boxes),boxes
                            result['desktop_first_two_actions']=boxes
                        # Open the linked weight/photo/account review using the real queue.
                        page.get_by_role('button',name=re.compile('Compare weights')).first.click()
                        page.get_by_role('heading',name='Check a weight difference',exact=True).wait_for()
                        page.get_by_text('The same photo file appears on both shipment records',exact=True).wait_for()
                        assert page.get_by_text(re.compile('Recorded stage location: Hub [A-D]')).is_visible()
                        assert page.get_by_text(re.compile('Post-delivery access:')).count()
                        capture('linked-case')
                        page.get_by_text(re.compile('Recorded stage location: Hub [A-D]')).evaluate("element => element.scrollIntoView({block:'start'})")
                        capture('handoff-facts')
                        assert page.get_by_role('heading',name='Account activity',exact=True).count()==1
                        assert not page.get_by_text(re.compile('permitted near-image candidates')).is_visible()
                        page.get_by_role('heading',name='Compare the recorded photos',exact=True).evaluate("element => element.scrollIntoView({block:'start'})")
                        capture('photo-comparison')
                        page.get_by_role('heading',name='AI review',exact=True).evaluate("element => element.scrollIntoView({block:'start'})")
                        capture('ai-review')
                        page.get_by_text('YOUR NEXT STEP',exact=True).evaluate("element => element.scrollIntoView({block:'start'})")
                        capture('next-step')
                        page.get_by_role('button',name=re.compile('Back to cases')).click()
                        page.get_by_role('heading',name='Cases to review',exact=True).wait_for()
                        select=page.get_by_test_id('stSelectbox').filter(has=page.get_by_text('Issue type',exact=True))
                        select.get_by_role('combobox').click();page.get_by_role('option',name='Data access',exact=True).click()
                        page.get_by_role('button',name=re.compile('Review access')).first.click()
                        page.get_by_role('heading',name='Check an access request',exact=True).wait_for()
                        assert page.get_by_role('heading',name='Account activity',exact=True).count()==1
                        capture('access-case')
                        page.get_by_role('button',name=re.compile('Back to cases')).click()
                        page.get_by_role('heading',name='Cases to review',exact=True).wait_for()
                        page.get_by_role('textbox',name='Search shipments, partners or issues').fill('PV-SHIP-021')
                        page.get_by_role('button',name='Find shipment',exact=True).click()
                        page.get_by_role('button',name=re.compile('Back to cases')).wait_for()
                        assert page.get_by_role('heading',name='Account activity',exact=True).count()==0
                        capture('shipment-case')
                        if width==390:
                            page.get_by_role('button',name=re.compile(r'\bMenu\b')).click()
                            page.get_by_role('button',name='Partners',exact=True).last.click()
                        else:page.get_by_role('button',name='Partners',exact=True).click()
                        page.get_by_text(re.compile('Finding outcomes:')).first.wait_for()
                        capture('partners')
                        context.close()
                    browser.close()
                result['status']='passed'
            finally:
                subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],capture_output=True)
                (OUT/'results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
if __name__=='__main__':main()
