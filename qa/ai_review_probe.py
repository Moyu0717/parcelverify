"""Public verification; --ai opts into exactly one synthetic investigation.

No retry loop, recovery token, provider payload, or credential is captured.
"""
import json,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

OUT=Path(__file__).parent/'artifacts/ai-ui-fix'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    result={'scope':'Public app, new isolated visitor workspace','live_requested':'--ai' in sys.argv,'ai_clicks':0}
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1366,'height':768})
        response=page.goto(sys.argv[1],wait_until='domcontentloaded',timeout=60000)
        result['http_status']=response.status
        for _ in range(120):
            wake=page.get_by_text('Yes, get this app back up!',exact=True)
            if not result.get('woke_sleeping_app') and wake.count() and wake.is_visible():
                wake.click();result['woke_sleeping_app']=True;page.wait_for_timeout(2000)
            frame=page.frame(url=re.compile(r'/~/\+/'))
            if frame:
                page.goto(frame.url,wait_until='domcontentloaded',timeout=60000);break
            if page.get_by_role('heading',name='Review workspace',exact=True).count():break
            page.wait_for_timeout(500)
        try:
            page.get_by_role('heading',name='Review workspace',exact=True).wait_for(timeout=90000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(OUT/'after-public-home.png'),full_page=True)
            result['home']=page.locator('body').inner_text()
            page.get_by_role('button',name=re.compile('Compare weights')).first.click()
            page.get_by_role('heading',name='Check a weight difference',exact=True).wait_for()
            page.wait_for_timeout(1000)
            result['case_before']=page.locator('body').inner_text()
            page.screenshot(path=str(OUT/'after-public-case.png'),full_page=True)
            page.get_by_role('button',name=re.compile('Workspace')).first.click()
            page.get_by_role('button',name='Settings',exact=True).click()
            page.get_by_role('heading',name='Settings',exact=True).wait_for()
            page.wait_for_timeout(2000)
            for label in ('Build information','AI connection diagnostics'):
                page.get_by_text(label,exact=True).click()
            page.wait_for_timeout(1000)
            result['settings_before']=page.locator('body').inner_text()
            page.screenshot(path=str(OUT/'after-public-settings.png'),full_page=True)
            expected=sys.argv[2]
            result['build_verified']=expected in result['settings_before'] and 'Loaded Python functions match the checked-out source.' in result['settings_before']
            if not result['build_verified']:raise RuntimeError('Expected checkout/loaded build not verified; no AI request sent')
            page.get_by_role('button',name='Home',exact=True).click()
            page.get_by_role('heading',name='Review workspace',exact=True).wait_for()
            page.get_by_role('button',name=re.compile('Compare weights')).first.click()
            page.get_by_role('heading',name='Check a weight difference',exact=True).wait_for()
            if '--ai' in sys.argv:
                action=page.get_by_role('button',name='Review evidence with AI',exact=True)
                if not action.is_enabled():raise RuntimeError('Groq configuration is not ready; no request sent')
                action.click();result['ai_clicks']=1
                page.get_by_role('button',name=re.compile('Retry AI review|Run another AI review')).wait_for(timeout=145000)
                page.get_by_text('AI review diagnostics',exact=True).click()
                with page.expect_download() as download:
                    page.get_by_role('button',name='Download AI diagnostic record',exact=True).click()
                record=json.loads(Path(download.value.path()).read_text(encoding='utf-8'))
                result['live_diagnostic']=record
                result['case_after']=page.locator('body').inner_text()
                page.screenshot(path=str(OUT/'after-public-ai.png'),full_page=True)
            # Read-only mobile checks share this synthetic workspace and cannot
            # trigger inference. They also exercise actual hosted navigation.
            page.set_viewport_size({'width':390,'height':844})
            page.get_by_role('button',name=re.compile(r'\bMenu\b')).click()
            page.get_by_role('button',name='Home',exact=True).last.click()
            expect(page.get_by_role('button',name=re.compile(r'\bMenu\b'))).to_have_attribute('aria-expanded','false',timeout=15000)
            page.get_by_role('heading',name='Review workspace',exact=True).wait_for()
            page.wait_for_timeout(1000)
            page.screenshot(path=str(OUT/'after-public-home-mobile.png'),full_page=True)
            result['mobile_home_overflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            page.get_by_role('button',name=re.compile('Compare weights')).first.click()
            page.get_by_role('heading',name='Check a weight difference',exact=True).wait_for()
            page.wait_for_timeout(1000)
            page.screenshot(path=str(OUT/'after-public-case-mobile.png'),full_page=True)
            result['mobile_case_overflow']=page.evaluate('document.documentElement.scrollWidth > innerWidth')
            result['runtime_exceptions']=page.get_by_test_id('stException').count()
            assert not result['mobile_home_overflow'] and not result['mobile_case_overflow'] and not result['runtime_exceptions']
            result['status']='checked'
        except Exception as error:
            result['status']='blocked';result['blocker']=str(error)[:1000]
            page.screenshot(path=str(OUT/'public-blocker.png'),full_page=True)
        finally:
            (OUT/'public-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            browser.close()
    print(json.dumps({key:value for key,value in result.items() if key not in ('home','case_before','case_after','settings_before')}))
if __name__=='__main__':main()
