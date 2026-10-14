"""Public demo scenario and responsive layout observations, no AI calls."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).parent/'artifacts'/'deployment'
result={'scope':'Public HTTPS; independent synthetic visitor contexts','views':[]}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    for width in (1440,390):
        page=browser.new_page(viewport={'width':width,'height':900})
        page.goto('https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/',wait_until='domcontentloaded',timeout=60000)
        for _ in range(40):
            frame=page.frame(url=re.compile(r'/~/\+/'))
            if frame:break
            page.wait_for_timeout(500)
        if frame:page.goto(frame.url,wait_until='domcontentloaded',timeout=60000)
        page.get_by_role('button',name=re.compile('Review cases')).wait_for(timeout=90000)
        def capture(name):
            page.wait_for_timeout(1500)
            item={'name':name,'width':width,'overflow':page.evaluate('document.documentElement.scrollWidth>innerWidth'),'exceptions':page.get_by_test_id('stException').count(),'body':page.locator('body').inner_text()}
            page.screenshot(path=str(OUT/f'public-{name}-{width}.png'),full_page=True)
            result['views'].append(item)
            assert not item['overflow'] and not item['exceptions']
        capture('home')
        for button,name in [('Compare weights','linked-case'),('Review explanation','supported-explanation'),('See missing information','insufficient-evidence')]:
            page.get_by_role('button',name=re.compile(button)).first.click()
            page.get_by_role('button',name=re.compile('Back to cases')).wait_for()
            capture(name)
            if name=='linked-case':
                page.get_by_text('Compare the recorded photos',exact=True).scroll_into_view_if_needed()
                capture('photo-comparison')
            page.get_by_role('button',name=re.compile('Back to cases')).click()
            page.wait_for_timeout(1000)
            if width<760:
                page.get_by_role('button',name=re.compile('Menu')).first.click()
                page.locator('.st-key-mobile-nav-Home').get_by_role('button').click()
                page.keyboard.press('Escape')
            else:page.locator('.st-key-nav-Home').get_by_role('button').click()
            page.get_by_role('button',name=re.compile('Review cases')).wait_for()
        page.close()
    browser.close()
result['status']='passed'
(OUT/'public-scenarios.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'status':result['status'],'views':len(result['views'])}))
