#!/usr/bin/env python3
"""
okonomi (お好み) Build Engine
=============================
Compiles, inlines, and encrypts standalone HTML apps and the portal hub using AES-256-GCM (PBKDF2-HMAC-SHA256).
Outputs self-decrypting static bundles into dist/ ready for GitHub Pages hosting.
"""

import argparse
import base64
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
DIST_DIR = ROOT_DIR / "dist"
PASSWORD_FILE = ROOT_DIR / "PASSWORD"
SHELL_TEMPLATE_FILE = TEMPLATES_DIR / "decryptor_shell.html"
PORTAL_TEMPLATE_FILE = TEMPLATES_DIR / "portal_template.html"

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


def extract_app_metadata(html_content: str, slug: str) -> Dict[str, str]:
    """Extract metadata (title, description, icon) from app HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text().strip() if title_tag else ""
    if not title:
        h1_tag = soup.find("h1")
        title = h1_tag.get_text().strip() if h1_tag else slug.replace("-", " ").replace("_", " ").title()

    # Strip generic suffix if present
    title = re.sub(r"\s*-\s*okonomi\s*$", "", title, flags=re.IGNORECASE).strip()

    # Description
    desc_meta = soup.find("meta", attrs={"name": "description"})
    desc = desc_meta.get("content", "").strip() if desc_meta else ""
    if not desc:
        p_tag = soup.find("p")
        desc = p_tag.get_text().strip()[:140] if p_tag else "Encrypted application"

    # Icon heuristic
    icon = "📱"
    if "test" in slug or "sandbox" in slug:
        icon = "🧪"
    elif "note" in slug or "doc" in slug:
        icon = "📝"
    elif "calc" in slug or "budget" in slug or "finance" in slug:
        icon = "📊"
    elif "travel" in slug or "trip" in slug:
        icon = "✈️"
    elif "tool" in slug or "util" in slug:
        icon = "🛠️"

    return {
        "slug": slug,
        "title": title,
        "desc": desc,
        "icon": icon,
    }


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


def build_portal_html(portal_template: str, apps_meta: List[Dict]) -> str:
    """Generates the unencrypted portal hub HTML containing the app directory."""
    cards_html = []
    for app in apps_meta:
        card = f"""
        <a href="./{app['slug']}/" class="app-card" data-title="{app['title']}" data-desc="{app['desc']}" data-slug="{app['slug']}">
          <div class="card-top">
            <div class="card-icon">{app['icon']}</div>
            <h2 class="card-title">{app['title']}</h2>
            <p class="card-desc">{app['desc']}</p>
          </div>
          <div class="card-footer">
            <span class="card-slug">/{app['slug']}</span>
            <span class="arrow">Open →</span>
          </div>
        </a>"""
        cards_html.append(card)

    rendered_cards = "\n".join(cards_html) if cards_html else "<p class='empty-state' style='display:block;'>No applications discovered in src/apps/</p>"
    return portal_template.replace("<!-- APP_CARDS_PLACEHOLDER -->", rendered_cards)


def main():
    parser = argparse.ArgumentParser(description="okonomi (お好み) static builder & encryptor")
    parser.add_argument("--generate-passphrase", action="store_true", help="Generate a secure master passphrase and exit")
    parser.add_argument("--password", type=str, help="Master password override")
    parser.add_argument("--clean", action="store_true", help="Clean dist/ folder before building")
    args = parser.parse_args()

    if args.generate_passphrase:
        passphrase = generate_passphrase()
        print("\n✨ Generated Master Passphrase:")
        print(f"   \033[1;32m{passphrase}\033[0m\n")
        print("Save this passphrase into the 'PASSWORD' file or keep it safe in your password manager.\n")
        return

    start_time = time.time()
    print("🍱 Building okonomi encrypted portal...")

    if not SHELL_TEMPLATE_FILE.exists():
        print(f"[!] Error: Missing decryptor shell template at {SHELL_TEMPLATE_FILE}")
        sys.exit(1)

    if not PORTAL_TEMPLATE_FILE.exists():
        print(f"[!] Error: Missing portal template at {PORTAL_TEMPLATE_FILE}")
        sys.exit(1)

    shell_template = SHELL_TEMPLATE_FILE.read_text(encoding="utf-8")
    portal_template = PORTAL_TEMPLATE_FILE.read_text(encoding="utf-8")

    password = get_password(args.password)

    # 1. Clean dist if requested
    if args.clean and DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Generate shared build salt and derive key
    salt = os.urandom(16)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    master_key = derive_key(password, salt)

    # 3. Discover and process apps
    discovered_apps = discover_apps()
    apps_meta = []

    print(f"📦 Discovered {len(discovered_apps)} app(s) in src/apps/:")

    for app in discovered_apps:
        slug = app["slug"]
        entry_file: Path = app["entry_file"]
        root_dir: Path = app["root_dir"]

        print(f"  • Inlining and bundling '{slug}' ({entry_file.relative_to(ROOT_DIR)})...")
        raw_html = entry_file.read_text(encoding="utf-8")
        inlined_html = inline_assets(raw_html, root_dir)
        meta = extract_app_metadata(inlined_html, slug)
        apps_meta.append(meta)

        # Encrypt app
        iv, ciphertext = encrypt_payload(inlined_html, master_key)
        iv_b64 = base64.b64encode(iv).decode("ascii")
        ciphertext_b64 = base64.b64encode(ciphertext).decode("ascii")

        app_dist_dir = DIST_DIR / slug
        app_dist_dir.mkdir(parents=True, exist_ok=True)
        app_dist_file = app_dist_dir / "index.html"

        encrypted_page_html = wrap_with_decryptor(
            shell_template,
            salt_b64,
            iv_b64,
            ciphertext_b64,
            meta["title"]
        )
        app_dist_file.write_text(encrypted_page_html, encoding="utf-8")
        print(f"    ✓ Encrypted -> dist/{slug}/index.html ({len(encrypted_page_html):,} bytes)")

    # 4. Build and encrypt Hub Portal
    print("🏠 Generating Hub Portal...")
    portal_html = build_portal_html(portal_template, apps_meta)
    p_iv, p_ciphertext = encrypt_payload(portal_html, master_key)
    p_iv_b64 = base64.b64encode(p_iv).decode("ascii")
    p_ciphertext_b64 = base64.b64encode(p_ciphertext).decode("ascii")

    encrypted_portal_html = wrap_with_decryptor(
        shell_template,
        salt_b64,
        p_iv_b64,
        p_ciphertext_b64,
        "Portal Hub"
    )
    portal_dist_file = DIST_DIR / "index.html"
    portal_dist_file.write_text(encrypted_portal_html, encoding="utf-8")
    print(f"    ✓ Encrypted Hub -> dist/index.html ({len(encrypted_portal_html):,} bytes)")

    # 5. Ensure .nojekyll for GitHub Pages
    nojekyll_file = DIST_DIR / ".nojekyll"
    nojekyll_file.touch()

    elapsed = time.time() - start_time
    print(f"\n✨ Build complete in {elapsed:.2f}s!")
    print(f"   Shared Salt: {salt_b64[:12]}...")
    print(f"   Output Directory: dist/ (Ready for GitHub Pages)")


if __name__ == "__main__":
    main()
