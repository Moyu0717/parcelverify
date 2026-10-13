"""Independent HTTPS browser inspection and real-model acceptance artifacts."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "qa" / "artifacts"

def navigate(page, title):
    page.get_by_test_id("stSidebar").get_by_text(title, exact=True).click()
    page.get_by_role("heading", name=title, exact=True).wait_for(timeout=30000)

def choose_case(page, shipment):
    selector = page.get_by_test_id("stSelectbox").filter(has=page.get_by_text("Case", exact=True))
    selector.get_by_role("combobox").click()
    page.get_by_role("option", name=re.compile(re.escape(shipment))).first.click()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--acceptance", action="store_true")
    parser.add_argument("--chrome", default="C:/Program Files/Google/Chrome/Application/chrome.exe")
    parser.add_argument("--ready-timeout", type=int, default=60000)
    parser.add_argument("--diagnose", action="store_true")
    args = parser.parse_args()
    if not args.url.startswith("https://"):
        raise ValueError("An HTTPS demo URL is required")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    evidence = {"url": args.url, "tested_at": datetime.now(timezone.utc).isoformat(), "checks": []}
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=args.chrome, headless=True)
            first = browser.new_context(viewport={"width": 1440, "height": 1080}, accept_downloads=True)
            page = first.new_page()
            network = {"failed_requests": [], "console_errors": [], "websocket_messages": {}, "frames": []}
            evidence["network"] = network
            page.on("requestfailed", lambda request: network["failed_requests"].append({"url": request.url.split("?")[0], "failure": request.failure}))
            page.on("console", lambda message: network["console_errors"].append(message.text[:400]) if message.type == "error" else None)
            def inspect_socket(socket):
                def inspect_message(payload):
                    try:
                        from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
                        message = ForwardMsg()
                        message.ParseFromString(payload)
                        kind = message.WhichOneof("type") or "unknown"
                        network["websocket_messages"][kind] = network["websocket_messages"].get(kind, 0) + 1
                        if kind == "delta" and message.delta.HasField("new_element"):
                            element = message.delta.new_element
                            if element.WhichOneof("type") in ("arrow_data_frame", "dataframe"):
                                import pyarrow as arrow
                                table = getattr(element, element.WhichOneof("type"))
                                if hasattr(table, "arrow_data"):
                                    table = table.arrow_data
                                records = arrow.ipc.open_stream(table.data).read_all().to_pylist()
                                for record in records:
                                    if record.get("error"):
                                        evidence.setdefault("run_diagnostics", []).append({key: record.get(key) for key in ("run_id", "status", "model_name", "error")})
                    except Exception:
                        network["websocket_messages"]["unparsed"] = network["websocket_messages"].get("unparsed", 0) + 1
                socket.on("framereceived", inspect_message)
            page.on("websocket", inspect_socket)
            response = page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
            if args.diagnose:
                page.wait_for_timeout(5000)
                network["frames"] = [frame.url for frame in page.frames]
                evidence["frame_content"] = []
                for frame in page.frames:
                    if frame.url.startswith(args.url.rstrip("/")):
                        evidence["frame_content"].append({"url": frame.url, "headings": frame.get_by_role("heading").all_text_contents(), "body": frame.locator("body").inner_text(timeout=5000)[:6000]})
                evidence.update(http_status=response.status if response else None, title=page.title(), page_url=page.url)
                body = page.locator("body").inner_text(timeout=5000)
                evidence["body_excerpt"] = re.sub(r"AIza[\w-]+", "[redacted]", body[:12000])
                if not re.search(r"AIza[\w-]+", body):
                    page.screenshot(path=str(ARTIFACTS / "remote-diagnostic.png"), full_page=True)
                evidence["status"] = "diagnostic_only"
                browser.close()
                return 1
            browser_page = page
            app_frame = None
            for _ in range(30):
                app_frame = page.frame(url=re.compile(r"/~/\+/"))
                if app_frame:
                    break
                page.wait_for_timeout(500)
            network["frames"] = [frame.url for frame in page.frames]
            if app_frame:
                browser_page.goto(app_frame.url, wait_until="domcontentloaded", timeout=60000)
                page = browser_page
            page.get_by_role("heading", name="Partner Overview", exact=True).wait_for(timeout=args.ready_timeout)
            browser_page.screenshot(path=str(ARTIFACTS / "remote-overview.png"), full_page=True)
            evidence.update(http_status=response.status if response else None, title=browser_page.title())
            evidence["checks"].append({"name": "independent_https_page", "status": "passed"})
            if not args.acceptance:
                evidence["body_excerpt"] = page.locator("body").inner_text()[:5000]
            else:
                for title in ("Shipment Timeline", "Access Monitoring", "Handoff Verification", "AI Investigation", "Approvals & Audit"):
                    navigate(page, title)
                    assert page.get_by_test_id("stException").count() == 0
                evidence["checks"].append({"name": "all_remote_pages", "status": "passed"})
                navigate(page, "AI Investigation")
                reports = []
                for label, shipment in [("main_exception", "PV-DEMO-001"), ("supported_repackaging", "PV-SHIP-011"), ("insufficient_evidence", "PV-SHIP-002")]:
                    choose_case(page, shipment)
                    page.get_by_role("button", name="Run AI investigation", exact=True).click()
                    success = page.get_by_text("Real model investigation saved.", exact=True)
                    failure = page.get_by_text(re.compile("Investigation incomplete:"))
                    success.or_(failure).wait_for(timeout=150000)
                    trace_button = page.get_by_role("button", name="Export investigation trace", exact=True)
                    if trace_button.count():
                        with browser_page.expect_download() as trace_download:
                            trace_button.click()
                        trace_download.value.save_as(ARTIFACTS / f"remote-{label}-trace.json")
                    if failure.count():
                        evidence["body_excerpt"] = page.locator("body").inner_text()[:10000]
                        raise AssertionError(f"{label}: {failure.inner_text()}")
                    with browser_page.expect_download() as download:
                        page.get_by_role("button", name="Export English report", exact=True).click()
                    destination = ARTIFACTS / f"remote-{label}.json"
                    download.value.save_as(destination)
                    report = json.loads(destination.read_text(encoding="utf-8"))
                    assert report["facts"] and all(f["evidence_ids"] for f in report["facts"])
                    assert "Tool execution trace" in page.locator("body").inner_text()
                    reports.append({"scenario": label, "case_id": report["case_id"], "verdict": report["verdict"], "artifact": str(destination)})
                    evidence["reports"] = reports
                    (ARTIFACTS / "remote-acceptance.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                evidence["checks"].append({"name": "three_actual_model_reports", "status": "passed"})
                second = browser.new_context(viewport={"width": 1440, "height": 1080})
                second_page = second.new_page()
                second_page.goto(args.url, wait_until="domcontentloaded", timeout=60000)
                second_frame = None
                for _ in range(30):
                    second_frame = second_page.frame(url=re.compile(r"/~/\+/"))
                    if second_frame:
                        break
                    second_page.wait_for_timeout(500)
                if second_frame:
                    second_page.goto(second_frame.url, wait_until="domcontentloaded", timeout=60000)
                second_page.get_by_role("heading", name="Partner Overview", exact=True).wait_for(timeout=60000)
                navigate(second_page, "AI Investigation")
                assert second_page.get_by_text("No completed AI report.", exact=False).count() == 1
                assert second_page.get_by_role("button", name="Export English report", exact=True).count() == 0
                evidence["checks"].append({"name": "independent_workspace_report_isolation", "status": "passed"})
                second.close()
            first.close()
            browser.close()
        evidence["status"] = "passed"
        return 0
    except Exception as error:
        evidence["status"] = "failed"
        evidence["error"] = str(error)[:2000]
        if "page" in locals() and not page.is_closed():
            try:
                body = page.locator("body").inner_text(timeout=5000)
                evidence["body_excerpt"] = re.sub(r"AIza[\w-]+", "[redacted]", body[:12000])
                evidence["page_url"] = page.url
                if not re.search(r"AIza[\w-]+", body):
                    page.screenshot(path=str(ARTIFACTS / "remote-error.png"), full_page=True)
            except Exception:
                pass
        return 1
    finally:
        destination = ARTIFACTS / ("remote-acceptance.json" if args.acceptance else "remote-probe.json")
        destination.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(json.dumps(evidence))

if __name__ == "__main__":
    raise SystemExit(main())
