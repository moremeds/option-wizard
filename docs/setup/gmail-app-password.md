# Gmail App Password Setup

The daily position scan delivers to chenxi.li08@outlook.com via Gmail SMTP. This requires a Gmail App Password from a Gmail account with 2FA enabled. The password lives outside the repo.

## Generate the password

1. Open https://myaccount.google.com/apppasswords (must be signed in as the Gmail sender).
2. Choose `Mail` and `Other (custom name)`, type "option-wizard", click Generate.
3. Copy the 16-character password. You will not see it again.

## Store the password

Two options. Pick one.

### A. Environment variable (simplest)

Append to `~/.zshrc`:

```bash
export GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
export GMAIL_SENDER_ADDRESS="your.sender@gmail.com"
```

Then `source ~/.zshrc`.

### B. Config file (preferred when running from cron)

```bash
mkdir -p ~/.config/option-wizard
cat > ~/.config/option-wizard/gmail.json <<'EOF'
{
  "sender_address": "your.sender@gmail.com",
  "app_password": "abcd efgh ijkl mnop"
}
EOF
chmod 600 ~/.config/option-wizard/gmail.json
```

`scripts/email_sender.py` reads env vars first, then falls back to this file.

## Verify

After setup, run:

```bash
.venv/bin/python -c "from scripts.email_sender import send_test; send_test('chenxi.li08@outlook.com')"
```

Check that the test email arrives. If not, check the error log at `~/.config/option-wizard/email-errors.log`.
