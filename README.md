# VAULT — Secure Password Vault

A desktop application for managing passwords, built with **Python** and **Tkinter**.

## Download

**Windows:** Download and run the [VAULT Setup v1.0.0](https://github.com/ShadowWolfSec/VAULT/releases/download/v1.0.0/VAULT_Setup.exe) installer.

## Features

### Security

- Encrypts data using **AES-256-GCM**.
- Derives keys using **Scrypt** (`N=131072`) and **HKDF-SHA256**, with **HMAC-SHA256** verification.
- Protects against repeated guessing attempts with an escalating delay: 2, 4, 8, 16, then 30 seconds.
- Automatically clears the clipboard after 30 seconds, with a visible countdown.
- Automatically locks the session after a configurable period of inactivity, and locks immediately when the window is minimized.
- Creates encrypted backups automatically whenever data is saved.
- Maintains an encrypted security activity log.
- Verifies the integrity of the vault file whenever it is opened.

### Account Management

- Add, edit, and delete accounts.
- View password strength: Weak, Medium, Strong, or Excellent.
- Get alerts for weak or duplicate passwords.
- Sort columns by clicking their headers, and search accounts instantly.
- Copy a password with one click.

### Import and Export

- Import CSV files directly from **Chrome** and **Firefox**.
- Export CSV files compatible with Chrome and Firefox.
- Open and manage multiple vaults stored in separate files.

### Interface

- Arabic and English language support.
- Light and dark themes.
- Tabs for Accounts, Security Analysis, Settings, and Activity Log.

## Requirements

| Requirement | Version or Notes |
|---|---|
| Python | 3.10 or later |
| `cryptography` | Latest version |
| Tkinter | Included with Python in most distributions; may need to be installed separately on some systems |

Install the required library:

```bash
pip install cryptography
```

## Run the Application

From the project directory, run:

```bash
python main.py
```

## Data Locations

Application data is stored in the following locations:

- **Windows:** `C:\Users\[username]\AppData\Local\VAULT\`
- **Linux and macOS:** `~/.local/share/VAULT/`

The main files and folders include:

```text
VAULT/
├── vault.dat              # Encrypted vault file
├── vault_settings.json    # Application settings
├── vault_security.log     # Activity log
└── .vault_backups/        # Automatic backups
```

Your data remains available when the application is updated or moved.

## Project Structure

```text
vault/
├── main.py
├── app.py
├── crypto.py
├── storage.py
├── security.py
├── password_utils.py
├── ui_dialogs.py
├── ui_widgets.py
├── i18n.py
├── theme.py
├── constants.py
├── performance.py
├── exceptions.py
└── README.md
```

## Encryption Overview

```text
Master password
       ↓
Scrypt (N=131072, r=8, p=1) + random salt (32 bytes)
       ↓
Master key (32 bytes)
       ↓
HKDF-SHA256
  ↙           ↘
Encryption key   HMAC key
  ↓
AES-256-GCM + random nonce (12 bytes)
  ↓
Encrypted data + HMAC-SHA256 verification
```

There is no hard-coded key in the code; keys are derived from the master password.

## Importing Passwords from a Browser

1. **Chrome:** Open Settings → Password Manager → Export passwords, then save the file as CSV.
2. **Firefox:** Open Settings → Privacy & Security → Saved Passwords → Export.
3. In VAULT, select **Import CSV** from the toolbar.

## Important Security Notes

- The master password cannot be recovered if lost. Keep it in a safe place.
- Exported CSV files are **not encrypted**. Delete them immediately after importing or using them.
- Backups are encrypted with the same master password.

## Developer

**Eng. RASHEED AL-RAJEHI @ SHADOW WOLF SECURITY**

---

> VAULT — Because your passwords deserve real protection.
