#!/usr/bin/env python3
"""
okonomi (お好み) Build Engine
=============================
Compiles, inlines, and encrypts standalone HTML apps using AES-256-GCM (PBKDF2-HMAC-SHA256).
Outputs self-decrypting static bundles into docs/<slug>/index.html ready for GitHub Pages hosting.
Maintains a stealth/empty home page at docs/index.html with zero hub directory links.
"""

import argparse
import base64
import hashlib
import mimetypes
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ROOT_DIR = Path(__file__).parent.resolve()
SRC_APPS_DIR = ROOT_DIR / "src" / "apps"
TEMPLATES_DIR = ROOT_DIR / "templates"
DOCS_DIR = ROOT_DIR / "docs"
PASSWORD_FILE = ROOT_DIR / "PASSWORD"
SHELL_TEMPLATE_FILE = TEMPLATES_DIR / "decryptor_shell.html"

PBKDF2_ITERATIONS = 600_000


def get_password(custom_password: Optional[str] = None) -> str:
    """Retrieve master password from argument, file, or prompt."""
    if custom_password:
        return custom_password.strip()

    if PASSWORD_FILE.exists():
        content = PASSWORD_FILE.read_text(encoding="utf-8").strip()
        if content:
            return content

    print(f"[-] Master password file not found at {PASSWORD_FILE}")
    pwd = input("Enter master password to encrypt apps: ").strip()
    if not pwd:
        print("[!] Error: Master password cannot be empty.")
        sys.exit(1)
    return pwd


def generate_passphrase() -> str:
    """Generates a memorable, high-entropy passphrase."""
    wordlist = [
        "autumn", "beacon", "breeze", "castle", "cedar", "cipher", "comet", "cosmos",
        "crystal", "drift", "ember", "falcon", "forest", "glacier", "harbor", "haven",
        "horizon", "island", "journey", "lagoon", "lantern", "meadow", "mirage", "nebula",
        "oasis", "ocean", "orbit", "pathway", "pebble", "phoenix", "planet", "prism",
        "quartz", "radiant", "ripple", "sanctuary", "shadow", "silence", "silver", "solace",
        "spark", "spectrum", "summit", "tempest", "thunder", "timber", "tide", "traverse",
        "valley", "velvet", "vessel", "voyage", "whisper", "wildwood", "zephyr"
    ]
    words = [secrets.choice(wordlist) for _ in range(5)]
    number = secrets.randbelow(900) + 100
    return f"{'-'.join(words)}-{number}"


def get_stable_salt(password: str) -> bytes:
    """Derive a stable 16-byte salt from the master password to preserve browser session caching across rebuilds."""
    salt_file = ROOT_DIR / ".salt"
    if salt_file.exists():
        try:
            salt_data = salt_file.read_bytes()
            if len(salt_data) >= 16:
                return salt_data[:16]
        except Exception:
            pass
    # Deterministic salt based on password + project pepper
    salt = hashlib.sha256(f"okonomi-salt-v1:{password}".encode("utf-8")).digest()[:16]
    return salt


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive 256-bit AES key via PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_payload(data_str: str, key: bytes) -> Tuple[bytes, bytes]:
    """Encrypt string using AES-256-GCM. Returns (iv, ciphertext_with_tag)."""
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, data_str.encode("utf-8"), None)
    return iv, ciphertext


def is_external_url(url: str) -> bool:
    """Check if a URL points to an external remote resource."""
    if not url:
        return True
    url_lower = url.lower().strip()
    return (
        url_lower.startswith("http://")
        or url_lower.startswith("https://")
        or url_lower.startswith("//")
        or url_lower.startswith("data:")
        or url_lower.startswith("#")
        or url_lower.startswith("mailto:")
        or url_lower.startswith("javascript:")
    )


def inline_assets(html_content: str, app_root_dir: Path) -> str:
    """Inlines local CSS, JS, and image assets into a single self-contained HTML document."""
    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Inline CSS <link rel="stylesheet" href="...">
    for link in soup.find_all("link", rel=lambda r: r and "stylesheet" in r):
        href = link.get("href")
        if href and not is_external_url(href):
            clean_href = href.split("?")[0].split("#")[0]
            css_path = (app_root_dir / clean_href).resolve()
            if css_path.exists() and css_path.is_file():
                try:
                    css_content = css_path.read_text(encoding="utf-8")
                    style_tag = soup.new_tag("style")
                    style_tag.string = css_content
                    link.replace_with(style_tag)
                except Exception as e:
                    print(f"  [!] Warning: Failed inlining CSS '{href}': {e}")

    # 2. Inline JavaScript <script src="...">
    for script in soup.find_all("script", src=True):
        src = script.get("src")
        if src and not is_external_url(src):
            clean_src = src.split("?")[0].split("#")[0]
            js_path = (app_root_dir / clean_src).resolve()
            if js_path.exists() and js_path.is_file():
                try:
                    js_content = js_path.read_text(encoding="utf-8")
                    script_tag = soup.new_tag("script")
                    if script.get("type"):
                        script_tag["type"] = script["type"]
                    script_tag.string = js_content
                    script.replace_with(script_tag)
                except Exception as e:
                    print(f"  [!] Warning: Failed inlining JS '{src}': {e}")

    # 3. Inline images <img src="...">
    for img in soup.find_all("img", src=True):
        src = img.get("src")
        if src and not is_external_url(src):
            clean_src = src.split("?")[0].split("#")[0]
            img_path = (app_root_dir / clean_src).resolve()
            if img_path.exists() and img_path.is_file():
                try:
                    mime, _ = mimetypes.guess_type(str(img_path))
                    if not mime:
                        mime = "application/octet-stream"
                    img_bytes = img_path.read_bytes()
                    b64_img = base64.b64encode(img_bytes).decode("ascii")
                    img["src"] = f"data:{mime};base64,{b64_img}"
                except Exception as e:
                    print(f"  [!] Warning: Failed inlining image '{src}': {e}")

    return str(soup)


def extract_app_title(html_content: str, slug: str) -> str:
    """Extract display title from app HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""
    if not title:
        h1_tag = soup.find("h1")
        title = h1_tag.get_text().strip() if h1_tag else slug.replace("-", " ").replace("_", " ").title()
    title = re.sub(r"\s*-\s*okonomi\s*$", "", title, flags=re.IGNORECASE).strip()
    return title


def discover_apps() -> List[Dict]:
    """Scans src/apps/ directory for apps (folders or standalone .html files)."""
    if not SRC_APPS_DIR.exists():
        SRC_APPS_DIR.mkdir(parents=True, exist_ok=True)
        return []

    apps = []
    for item in sorted(SRC_APPS_DIR.iterdir()):
        if item.name.startswith("."):
            continue

        if item.is_dir():
            index_file = item / "index.html"
            if index_file.exists():
                apps.append({
                    "slug": item.name,
                    "entry_file": index_file,
                    "root_dir": item,
                })
        elif item.is_file() and item.suffix.lower() == ".html":
            slug = item.stem
            apps.append({
                "slug": slug,
                "entry_file": item,
                "root_dir": SRC_APPS_DIR,
            })

    return apps


def wrap_with_decryptor(
    shell_template: str,
    salt_b64: str,
    iv_b64: str,
    ciphertext_b64: str,
    title: str
) -> str:
    """Wraps ciphertext payload into the self-decrypting shell HTML."""
    payload_json = f"""<script id="okonomi-data" type="application/json">
{{
  "salt": "{salt_b64}",
  "iv": "{iv_b64}",
  "ciphertext": "{ciphertext_b64}",
  "title": "{title}"
}}
</script>"""

    if "<!-- PAYLOAD_PLACEHOLDER -->" in shell_template:
        return shell_template.replace("<!-- PAYLOAD_PLACEHOLDER -->", payload_json)
    return shell_template.replace("</body>", f"{payload_json}\n</body>")


def main():
    parser = argparse.ArgumentParser(description="okonomi (お好み) static builder & encryptor")
    parser.add_argument("--generate-passphrase", action="store_true", help="Generate a secure master passphrase and exit")
    parser.add_argument("--password", type=str, help="Master password override")
    parser.add_argument("--clean", action="store_true", help="Clean docs/ folder before building")
    args = parser.parse_args()

    if args.generate_passphrase:
        passphrase = generate_passphrase()
        print("\n✨ Generated Master Passphrase:")
        print(f"   \033[1;32m{passphrase}\033[0m\n")
        print("Save this passphrase into the 'PASSWORD' file or keep it safe in your password manager.\n")
        return

    start_time = time.time()
    print("🍱 Building okonomi encrypted apps...")

    if not SHELL_TEMPLATE_FILE.exists():
        print(f"[!] Error: Missing decryptor shell template at {SHELL_TEMPLATE_FILE}")
        sys.exit(1)

    shell_template = SHELL_TEMPLATE_FILE.read_text(encoding="utf-8")
    password = get_password(args.password)

    # 1. Clean docs if requested
    if args.clean and DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Derive stable build salt and key
    salt = get_stable_salt(password)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    master_key = derive_key(password, salt)

    # 3. Discover and process apps
    discovered_apps = discover_apps()

    print(f"📦 Discovered {len(discovered_apps)} app(s) in src/apps/:")

    for app in discovered_apps:
        slug = app["slug"]
        entry_file: Path = app["entry_file"]
        root_dir: Path = app["root_dir"]

        print(f"  • Inlining and bundling '{slug}' ({entry_file.relative_to(ROOT_DIR)})...")
        raw_html = entry_file.read_text(encoding="utf-8")
        inlined_html = inline_assets(raw_html, root_dir)
        title = extract_app_title(inlined_html, slug)

        # Encrypt app
        iv, ciphertext = encrypt_payload(inlined_html, master_key)
        iv_b64 = base64.b64encode(iv).decode("ascii")
        ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")

        app_docs_dir = DOCS_DIR / slug
        app_docs_dir.mkdir(parents=True, exist_ok=True)
        app_docs_file = app_docs_dir / "index.html"

        encrypted_page_html = wrap_with_decryptor(
            shell_template,
            salt_b64,
            iv_b64,
            ciphertext_b64,
            title
        )
        app_docs_file.write_text(encrypted_page_html, encoding="utf-8")
        print(f"    ✓ Encrypted -> docs/{slug}/index.html ({len(encrypted_page_html):,} bytes)")

    # 4. Generate Stealth Home Page (No Directory / Hub Listing)
    stealth_index_file = DOCS_DIR / "index.html"
    stealth_index_file.write_text(
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head><meta charset=\"UTF-8\"><title></title></head>\n<body></body>\n</html>\n",
        encoding="utf-8"
    )
    print("  • Created stealth root page at docs/index.html (zero links)")

    # 5. Ensure .nojekyll for GitHub Pages
    nojekyll_file = DOCS_DIR / ".nojekyll"
    nojekyll_file.touch()

    elapsed = time.time() - start_time
    print(f"\n✨ Build complete in {elapsed:.2f}s!")
    print(f"   Shared Salt: {salt_b64[:12]}...")
    print(f"   Output Directory: docs/ (Ready for GitHub Pages)")


if __name__ == "__main__":
    main()
