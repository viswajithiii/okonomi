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
│ - quick-notes.html            │           │ - index.html (encrypted portal hub)     │
│ - budget-calc/index.html      │           │ - test_page/index.html (encrypted app)  │
└───────────────────────────────┘           └─────────────────────────────────────────┘
```

- **Encryption**: AES-256-GCM with PBKDF2-HMAC-SHA256 (600,000 iterations).
- **Single-Unlock UX**: All apps within a build share a single cryptographic salt. Entering your master password once unlocks the hub and all apps across the domain with **0ms instant decryption** via cached key in `localStorage`.
- **Cache Invalidation**: Rebuilding with a new salt automatically clears stale cached keys and gracefully re-prompts for the password.
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
  <a href="../">← Back to Hub</a>
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
Navigate to `http://localhost:8000/` and unlock with your master password.

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
│   ├── decryptor_shell.html   # Standalone self-decrypting client bootstrap
│   └── portal_template.html   # Portal hub launcher template
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
    ├── index.html             # Encrypted hub portal
    └── test_page/
        └── index.html         # Self-decrypting test page
```

---

## ⚙️ GitHub Pages Setup

To serve your encrypted portal via GitHub Pages:
1. In your GitHub repository, go to **Settings** → **Pages**.
2. Under **Build and deployment** → **Source**, select **Deploy from a branch**.
3. Choose your branch (e.g. `main`) and folder (`/dist` if supported by your setup, or deploy the `dist/` contents to `gh-pages` branch).

---

## 🔒 Security Guarantees

1. **Zero Server Knowledge**: GitHub and any intermediary CDN only see AES-256-GCM ciphertext and the static decryptor shell.
2. **GPU Cracking Resistance**: 600,000 PBKDF2 iterations ensure brute-force resistance against offline attackers.
3. **No External CDN Dependencies**: The decryptor shell runs 100% offline with zero external network dependencies.
