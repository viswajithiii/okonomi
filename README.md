# 🍱 okonomi (お好み)

> *"As you like it" / "Custom choice"* — A centralized, GitHub-synced repository hosting one-off HTML apps, mini-tools, and private dashboards—fully encrypted at rest, served via GitHub Pages, and unified under a single-unlock password system.

---

## 🔒 Security Architecture (Zero-Leak by Design)

```text
Local Machine (Plaintext)                    GitHub & Public Internet (Ciphertext Only)
┌───────────────────────────────┐           ┌─────────────────────────────────────────┐
│ PASSWORD (gitignored)         │           │ build.py, deploy.sh, dev.sh (tracked)   │
│ src/apps/ (gitignored)        │  ───────► │ templates/ (tracked generic templates)  │
│ - test_page/index.html        │  build.py │ dist/ (tracked AES-256-GCM ciphertext)  │
│ - quick-notes.html            │           │ - index.html (stealth blank root)       │
│ - budget-calc/index.html      │           │ - test_page/index.html (encrypted app)  │
└───────────────────────────────┘           └─────────────────────────────────────────┘
```

- **Direct Stealth URLs**: No hub of links is published on the home page. Apps live strictly at their designated path (e.g. `/test_page/`), maintaining stealth.
- **Encryption**: AES-256-GCM with PBKDF2-HMAC-SHA256 (600,000 iterations).
- **Single-Unlock UX**: Entering your master password once on any app unlocks all apps across the domain with **0ms instant decryption** via cached key in `localStorage`.
- **Strict Separation**: Master password and raw plaintext source code (`src/apps/`) are strictly gitignored and never leave your local machine.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.9+ and [`uv`](https://github.com/astral-sh/uv)

### 2. Set Master Password
Create a `PASSWORD` file in the root of the repository:
```bash
echo "your-super-secret-passphrase" > PASSWORD
```
*(Or generate a secure passphrase using `uv run python build.py --generate-passphrase`)*

### 3. Add an App
Create an app directory inside `src/apps/`:
```bash
mkdir -p src/apps/my-app
cat << 'EOF' > src/apps/my-app/index.html
<!DOCTYPE html>
<html>
<head><title>My App</title></head>
<body>
  <h1>Hello from Encrypted App!</h1>
</body>
</html>
EOF
```
*Note: `build.py` automatically inlines local CSS, JS scripts, and images into the encrypted bundle.*

### 4. Preview Locally
Start the local preview server:
```bash
./dev.sh
```
Navigate to `http://localhost:8000/test_page/` and unlock with your master password.

### 5. Deploy to GitHub Pages
Run the deployment script (includes automated safety checks to prevent plaintext leaks):
```bash
./deploy.sh "Add my-app"
```

---

## 📁 Repository Structure

```text
okonomi/
├── PASSWORD                   # [GITIGNORED] Local master password
├── .gitignore                 # Enforces ignoring PASSWORD and src/apps/
├── pyproject.toml             # uv package and dependency configuration
├── build.py                   # Inliner, bundler, and AES-256-GCM encryptor
├── dev.sh                     # Local preview server
├── deploy.sh                  # Safe commit & push with leak verification
├── README.md                  # Documentation
│
├── templates/                 # [TRACKED] Generic UI templates (zero secrets)
│   └── decryptor_shell.html   # Standalone self-decrypting client bootstrap
│
├── src/
│   └── apps/                  # [GITIGNORED] Raw plaintext source apps
│       └── test_page/         # Test verification sandbox
│           ├── index.html
│           ├── style.css
│           └── app.js
│
└── dist/                      # [TRACKED] AES-256-GCM encrypted artifacts
    ├── .nojekyll              # GitHub Pages Jekyll bypass
    ├── index.html             # Stealth empty root
    └── test_page/
        └── index.html         # Self-decrypting test page
```
