#!/usr/bin/env python3
"""Sanitize the repo tree before publishing: strip subscription/tenant IDs,
public IPs, and SSH keys. Private RFC1918 IPs are retained (harmless).
Idempotent - safe to run repeatedly. Run AFTER measurements are collected.
"""
import re, os, glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Concrete secret values (subscription id on line 1, then one public IP per line)
# live in a git-ignored local file so this script itself carries no secrets.
SECRETS_FILE = os.path.join(BASE, "scripts", "redact-values.local.txt")
SUB_ID = ""
PUBLIC_IPS = []
if os.path.exists(SECRETS_FILE):
    with open(SECRETS_FILE) as fh:
        vals = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    if vals:
        SUB_ID, PUBLIC_IPS = vals[0], vals[1:]

GUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                     r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")
SSH_RE = re.compile(r"ssh-(rsa|ed25519)\s+\S+")

TARGETS = (
    glob.glob(os.path.join(BASE, "scripts", "*.py")) +
    glob.glob(os.path.join(BASE, "scripts", "*.yaml")) +
    glob.glob(os.path.join(BASE, "raw-output", "*.json")) +
    glob.glob(os.path.join(BASE, "raw-output", "*.csv")) +
    glob.glob(os.path.join(BASE, "*.md"))
)

def sanitize(text):
    for ip in PUBLIC_IPS:
        text = text.replace(ip, "PUBLIC_IP_REDACTED")
    text = text.replace(SUB_ID, "SUBSCRIPTION_ID_REDACTED")
    text = GUID_RE.sub("GUID_REDACTED", text)
    text = SSH_RE.sub("SSH_KEY_REDACTED", text)
    return text

def main():
    changed = 0
    for path in TARGETS:
        if os.path.basename(path) == "sanitize.py":
            continue
        with open(path, encoding="utf-8") as fh:
            orig = fh.read()
        new = sanitize(orig)
        if new != orig:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new)
            changed += 1
            print(f"sanitized: {os.path.relpath(path, BASE)}")
    print(f"Done. {changed} file(s) modified.")

if __name__ == "__main__":
    main()
