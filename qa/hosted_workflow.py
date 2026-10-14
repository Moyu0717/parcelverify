"""Consequential public acceptance in a fresh synthetic visitor workspace."""
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT=Path(__file__).parent/'artifacts'/'deployment'
OUT.mkdir(parents=True,exist_ok=True)
result={'scope':'Public HTTPS; isolated fresh browser workspace','checks':[]}
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
        page.get_by_role('button',name=re.compile('Review cases')).wait_for(timeout=90000)
        page.get_by_role('button',name=re.compile('Compare weights')).first.click()
        page.get_by_text('5 identifiable findings across 2 permitted shipments.',exact=False).wait_for()
        result['checks'].append('linked weight/photo/access findings visible')
        assert page.locator('img').evaluate_all('(xs)=>xs.every(x=>x.complete&&x.naturalWidth>0)')
        page.get_by_role('button',name='Send request for approval',exact=True).click()
        print('Proposal submitted',flush=True)
        page.get_by_text('I reviewed this request and its evidence.',exact=True).click()
        page.get_by_role('button',name='Approve request',exact=True).click()
        page.get_by_role('button',name='Apply approved step',exact=True).click()
        print('Approved step applied',flush=True)
        page.get_by_text('Supply evidence',exact=True).click()
        page.get_by_label('New weight (kg)',exact=True).fill('2.00')
        page.get_by_label('Evidence or explanation',exact=True).fill('Synthetic acceptance check: a fresh scale measurement, recorded for human review.')
        page.get_by_role('button',name='Submit evidence for review',exact=True).click()
        page.get_by_label('Review reason',exact=True).fill('Checked the recorded response; other linked findings remain unresolved.')
        page.get_by_role('button',name='Accept evidence',exact=True).click()
        print('Submitted evidence accepted',flush=True)
        page.get_by_text('The latest weight matches the expectation;',exact=False).wait_for()
        page.wait_for_timeout(1500)
        page.get_by_text('Review findings and record an outcome',exact=True).click()
        page.wait_for_timeout(1000)
        page.get_by_label('Closure reason',exact=True).fill('Closing synthetic acceptance case with unresolved photo reuse and access findings explicitly retained.')
        confirmation=page.get_by_label('I reviewed the linked findings and the stated closure outcome.')
        confirmation.focus();confirmation.press('Space')
        assert confirmation.is_checked()
        page.get_by_role('button',name='Close case',exact=True).click()
        page.get_by_text(re.compile('Case closed:')).wait_for()
        page.screenshot(path=str(OUT/'public-workflow-closed.png'),full_page=True)
        page.get_by_text('Activity',exact=True).click()
        page.get_by_text('Audit details',exact=True).click()
        with page.expect_download() as download:
            page.get_by_role('button',name='Download audit record',exact=True).click()
        path=OUT/'public-workflow-audit.json';download.value.save_as(path)
        audit=json.loads(path.read_text())
        result['audit_keys']=list(audit)
        result['checks'].append('approval â†’ one task â†’ submission â†’ acceptance â†’ unresolved closure â†’ audit export')
        result['audit_summary']={k:len(v) for k,v in audit.items() if isinstance(v,list)}
        assert audit['decisions'][-1]['outcome']=='closed_unresolved'
        result['status']='passed'
    except Exception as e:
        result['status']='failed';result['error']=str(e)[:1500]
        result['body']=page.locator('body').inner_text()[:14000]
        page.screenshot(path=str(OUT/'public-workflow-error.png'),full_page=True)
    finally:
        (OUT/'public-workflow.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result));browser.close()
