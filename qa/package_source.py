"""Build an allowlisted, secret-free source archive and GitHub upload payloads."""
import base64
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    names = ["app.py", "start.py", "workspace.py", "db.py", "seed.py", "contracts.py", "schema.sql",
             "requirements.txt", "requirements-lock.txt", "requirements-qa.txt", "README.md", ".gitignore", ".dockerignore",
             ".env.example", "Dockerfile", ".streamlit/config.toml"]
    for directory in ("agent", "services", "ui", "tests", "docs", "qa", "fixtures"):
        names.extend(str(file.relative_to(ROOT)).replace("\\", "/") for file in (ROOT / directory).rglob("*")
                     if file.is_file() and "__pycache__" not in file.parts and "artifacts" not in file.parts
                     and file.suffix in (".py", ".md", ".jpg", ".css"))
    names.append("reference/ParcelVerify_Codex_Handoff_Workflow.md")
    names.append("reference/ParcelVerify_UI_Refactor.md")
    manifest, batch, batches, size = [], [], [], 0
    archive = output / "ParcelVerify-source.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(set(names)):
            content = (ROOT / name).read_bytes()
            bundle.writestr(name, content)
            manifest.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
            binary = name.endswith(".jpg")
            value = base64.b64encode(content).decode() if binary else content.decode("utf-8-sig")
            entry = {"path": name, "encoding": "base64" if binary else "utf-8", "content": value}
            if size + len(value) > 25000 and batch:
                batches.append(batch)
                batch, size = [], 0
            batch.append(entry)
            size += len(value)
    if batch:
        batches.append(batch)
    for index, entries in enumerate(batches):
        (output / f"publish-{index}.json").write_text(json.dumps(entries), encoding="utf-8")
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result = {"archive": str(archive), "files": len(manifest), "batches": len(batches),
              "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    (output / "package-result.json").write_text(json.dumps(result), encoding="utf-8")
    print(json.dumps(result))

if __name__ == "__main__":
    main()
