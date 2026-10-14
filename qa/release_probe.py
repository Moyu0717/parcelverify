"""Read-only public release evidence in an independent visitor session."""
import json
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / 'artifacts' / 'deployment'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe', headless=True)
    page = browser.new_page(viewport={'width':1440,'height':1000})
    response = page.goto(sys.argv[1], wait_until='domcontentloaded', timeout=60000)
    for _ in range(40):
        frame = page.frame(url=re.compile(r'/~/\+/'))
        if frame: break
        page.wait_for_timeout(500)
    if frame: page.goto(frame.url, wait_until='domcontentloaded', timeout=60000)
    page.get_by_role('heading', name='Settings', exact=True).or_(page.get_by_role('button', name='Settings', exact=True)).or_(page.get_by_text('Needs review', exact=True)).first.wait_for(timeout=90000)
    page.wait_for_timeout(3000)
    result = {'http_status': response.status, 'url':page.url,'home':page.locator('body').inner_text(), 'links':page.locator('a').evaluate_all('(xs)=>xs.map(x=>({text:x.innerText,url:x.href}))')}
    page.screenshot(path=str(OUT/'public-home.png'), full_page=True)
    weight=page.get_by_role('button',name=re.compile('Compare weights')).first
    if weight.count():
        weight.click(); page.wait_for_timeout(2000)
        result['case']=page.locator('body').inner_text()
        result['images']=page.locator('img').evaluate_all('(xs)=>xs.map(x=>({alt:x.alt,loaded:x.complete&&x.naturalWidth>0}))')
        ai=page.get_by_role('button',name='Explain this issue with AI',exact=True)
        result['ai_enabled']=bool(ai.count() and ai.is_enabled())
        if '--ai' in sys.argv and result['ai_enabled']:
            ai.click()
            page.get_by_role('button',name='Retry AI explanation',exact=True).or_(page.get_by_text('AI explanation saved. Review it before deciding.',exact=True)).wait_for(timeout=145000)
            result['after_ai']=page.locator('body').inner_text()
            technical=page.get_by_text('Technical details',exact=True)
            if technical.count(): technical.first.click(); page.wait_for_timeout(500)
            result['ai_details']=page.locator('body').inner_text()
        page.screenshot(path=str(OUT/'public-case.png'),full_page=True)
    workspace = page.get_by_role('button', name=re.compile('Workspace'))
    if workspace.count(): workspace.first.click(); page.wait_for_timeout(500)
    settings = page.get_by_role('button', name='Settings', exact=True)
    if settings.count():
        settings.click(); page.wait_for_timeout(2000)
        for label in ['Build information','AI connection diagnostics']:
            item=page.get_by_text(label,exact=True)
            if item.count(): item.first.click(); page.wait_for_timeout(500)
        result['settings']=page.locator('body').inner_text()
        page.screenshot(path=str(OUT/'public-settings.png'),full_page=True)
    (OUT/'public-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    browser.close()
