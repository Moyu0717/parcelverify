"""Record human supported findings and verified closure on isolated scenario B."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(__file__).parent/'artifacts'/'deployment'
result={'scope':'Public HTTPS; fresh synthetic supported-explanation case'}
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
    page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
    try:
        page.goto('https://parcelverify-fhu5hezcatyb5ko932spwg.streamlit.app/',wait_until='domcontentloaded',timeout=60000)
        for _ in range(40):
            frame=page.frame(url=re.compile(r'/~/\+/'))
            if frame:break
            page.wait_for_timeout(500)
        if frame:page.goto(frame.url,wait_until='domcontentloaded',timeout=60000)
        page.get_by_role('button',name=re.compile('Review explanation')).wait_for(timeout=90000)
        page.get_by_role('button',name=re.compile('Review explanation')).click()
        page.get_by_text('Review findings and record an outcome',exact=True).click()
        page.wait_for_timeout(1000)
        forms=page.get_by_test_id('stForm').filter(has=page.get_by_role('button',name='Record finding review',exact=True))
        result['finding_count']=forms.count()
        for index in range(forms.count()):
            form=forms.nth(index)
            choice=form.get_by_test_id('stSelectbox').get_by_role('combobox')
            choice.focus();page.keyboard.press('ArrowDown')
            page.get_by_text('supported',exact=True).last.click()
            page.wait_for_timeout(500)
            form.get_by_test_id('stMultiSelect').get_by_role('combobox').click()
            options=page.get_by_role('option').all_text_contents()
            result.setdefault('source_options',options)
            matching=page.get_by_role('option',name=re.compile('Repack|repack|Handed over|account activity'))
            if matching.count():matching.first.click()
            else:page.get_by_role('option').first.click()
            page.keyboard.press('Escape')
            form.get_by_label('Finding review reason',exact=True).fill('Synthetic manual review: approved packaging and checked scales support the measurement; the export is within recorded authorization.')
            form.get_by_role('button',name='Record finding review',exact=True).click()
            page.wait_for_timeout(1500)
        closure=page.get_by_test_id('stForm').filter(has=page.get_by_role('button',name='Close case',exact=True))
        choice=closure.get_by_test_id('stSelectbox').get_by_role('combobox')
        choice.focus();page.keyboard.press('ArrowDown')
        page.get_by_text('Verified and resolved',exact=True).last.click()
        closure.get_by_label('Closure reason',exact=True).fill('Synthetic human acceptance: linked findings have supported explanations and no required measurements are unknown.')
        closure.get_by_test_id('stMultiSelect').get_by_role('combobox').click()
        matching=page.get_by_role('option',name=re.compile('Repack|repack|Handed over'))
        if matching.count():matching.first.click()
        else:page.get_by_role('option').first.click()
        page.keyboard.press('Escape')
        checkbox=page.get_by_label('I reviewed the linked findings and the stated closure outcome.')
        checkbox.focus();checkbox.press('Space');assert checkbox.is_checked()
        page.get_by_role('button',name='Close case',exact=True).click()
        page.get_by_text(re.compile('Case closed:')).wait_for()
        page.screenshot(path=str(OUT/'public-verified-closure.png'),full_page=True)
        page.get_by_text('Activity',exact=True).click();page.get_by_text('Audit details',exact=True).click()
        with page.expect_download() as d:page.get_by_role('button',name='Download audit record',exact=True).click()
        path=OUT/'public-verified-audit.json';d.value.save_as(path)
        audit=json.loads(path.read_text());assert audit['decisions'][-1]['outcome']=='verified_resolved'
        result['status']='passed'
    except Exception as e:
        result['status']='failed';result['error']=str(e)[:1500];result['body']=page.locator('body').inner_text()[:16000]
        page.screenshot(path=str(OUT/'public-verified-error.png'),full_page=True)
    finally:
        print(json.dumps(result));(OUT/'public-verified-closure.json').write_text(json.dumps(result,indent=2),encoding='utf-8');browser.close()
