import pathlib, re, shutil

root = pathlib.Path("templates")
for p in root.rglob("*.html"):
    text = p.read_text(encoding="utf-8")
    new  = re.sub(r"url_for\('static',\s*filename=", "url_for('static', path=", text)
    if text != new:
        shutil.copy(p, p.with_suffix(".bak"))   # lav .bak-backup
        p.write_text(new, encoding="utf-8")
        print(f"  patched {p}")
print("✓  Færdig – alle 'filename=' er nu ændret til 'path='")
