"""Clean backend/.env: dedupe, organize, and make provider state honest.

Prints only a key-level summary - never any values.
"""
import io

PATH = r"c:\Users\M.T.LaptoppoinT\Desktop\devops_monitor_pro\backend\.env"

PLACEHOLDER_MARKERS = ("your-", "change-me", "example", "placeholder", "platform-", "xxx", "todo")


def is_real(value):
    v = value.strip().strip('"').strip("'")
    if not v:
        return False
    lv = v.lower()
    return not any(m in lv for m in PLACEHOLDER_MARKERS)


def load_values(path):
    """Parse .env with dotenv last-wins semantics."""
    values = {}
    dupes = []
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        for i, raw in enumerate(f, 1):
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if key in values:
                dupes.append(key)
            values[key] = value.strip()
    return values, dupes


def main():
    values, dupes = load_values(PATH)
    print(f"parsed keys: {len(values)} | duplicate keys found: {len(dupes)}")

    def preserved(key, default=""):
        return values.get(key, default)

    # ---- Provider state: honest configuration ----------------------------
    # A provider stays DISABLED unless its required credentials are real.
    smtp_user = preserved("SMTP_USERNAME")
    smtp_pass = preserved("SMTP_PASSWORD")
    smtp_from = preserved("SMTP_FROM_EMAIL")
    smtp_complete = is_real(smtp_user) and is_real(smtp_pass) and is_real(smtp_from)
    smtp_enabled = "true" if smtp_complete else "false"

    wa_pid = preserved("WHATSAPP_PHONE_NUMBER_ID")
    wa_token = preserved("WHATSAPP_ACCESS_TOKEN")
    wa_complete = is_real(wa_pid) and is_real(wa_token)
    wa_enabled = "true" if wa_complete else "false"

    tg_token = preserved("TELEGRAM_BOT_TOKEN")
    tg_enabled = "true" if is_real(tg_token) else "false"

    actions = []
    if preserved("SMTP_ENABLED", "false").lower() != smtp_enabled:
        actions.append("SMTP_ENABLED -> false (SMTP credentials not fully configured)")
    if preserved("WHATSAPP_ENABLED", "false").lower() != wa_enabled:
        actions.append("WHATSAPP_ENABLED -> false (WhatsApp credentials empty)")
    if preserved("TELEGRAM_ENABLED", "false").lower() != tg_enabled:
        actions.append("TELEGRAM_ENABLED -> false (Telegram bot token empty)")
    for key, val in (("SMTP_USERNAME", smtp_user), ("SMTP_PASSWORD", smtp_pass), ("SMTP_FROM_EMAIL", smtp_from)):
        if val and not is_real(val):
            actions.append(f"{key} -> cleared (was placeholder-like)")
            values[key] = ""

    template = f"""# ============================================================
# DevOps Monitor Pro - backend environment configuration
# Single source of truth for local deployment (loaded when the
# backend is started from this backend/ directory).
# Reference for all supported keys: .env.example
#
# SECURITY: provider credentials are PLATFORM-MANAGED and stay
# server-side only. They are never returned to clients by the API.
# Providers remain disabled until their real credentials are set.
# ============================================================

# ---- Database ----
MONGODB_URI={preserved("MONGODB_URI", "mongodb://localhost:27017")}

# ---- JWT / Security ----
SECRET_KEY={preserved("SECRET_KEY")}
ALGORITHM={preserved("ALGORITHM", "HS256")}
ACCESS_TOKEN_EXPIRE_MINUTES={preserved("ACCESS_TOKEN_EXPIRE_MINUTES", "30")}

# ---- CORS ----
FRONTEND_URL={preserved("FRONTEND_URL", "http://localhost:8501")}

# ---- Cache (optional) ----
REDIS_URL={preserved("REDIS_URL")}

# ---- Email provider (platform SMTP) ----
# Clients only configure their recipient email. Enable once the
# server/port/username/password/from email below are real values.
SMTP_ENABLED={smtp_enabled}
SMTP_SERVER={preserved("SMTP_SERVER", "smtp.gmail.com")}
SMTP_PORT={preserved("SMTP_PORT", "587")}
SMTP_USERNAME={values.get("SMTP_USERNAME", "")}
SMTP_PASSWORD={values.get("SMTP_PASSWORD", "")}
SMTP_USE_TLS={preserved("SMTP_USE_TLS", "true")}
SMTP_FROM_EMAIL={values.get("SMTP_FROM_EMAIL", "")}
SMTP_FROM_NAME={preserved("SMTP_FROM_NAME", "DevOps Monitor Pro")}

# ---- WhatsApp provider (Meta WhatsApp Cloud API) ----
# Clients only connect their destination phone number. Enable once
# WHATSAPP_PHONE_NUMBER_ID and WHATSAPP_ACCESS_TOKEN are real values.
WHATSAPP_ENABLED={wa_enabled}
WHATSAPP_API_URL={preserved("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0")}
WHATSAPP_PHONE_NUMBER_ID={preserved("WHATSAPP_PHONE_NUMBER_ID")}
WHATSAPP_ACCESS_TOKEN={preserved("WHATSAPP_ACCESS_TOKEN")}
WHATSAPP_TIMEOUT={preserved("WHATSAPP_TIMEOUT", "30")}

# ---- Telegram provider (one platform bot) ----
# Clients connect via one-time tokens. Enable once TELEGRAM_BOT_TOKEN
# is a real value. WEBHOOK_SECRET verifies Telegram webhook calls.
TELEGRAM_ENABLED={tg_enabled}
TELEGRAM_BOT_TOKEN={preserved("TELEGRAM_BOT_TOKEN")}
TELEGRAM_TIMEOUT={preserved("TELEGRAM_TIMEOUT", "30")}
TELEGRAM_PARSE_MODE={preserved("TELEGRAM_PARSE_MODE", "HTML")}
TELEGRAM_BOT_USERNAME={preserved("TELEGRAM_BOT_USERNAME")}
TELEGRAM_WEBHOOK_SECRET={preserved("TELEGRAM_WEBHOOK_SECRET")}
TELEGRAM_CONNECT_TOKEN_EXPIRE_MINUTES={preserved("TELEGRAM_CONNECT_TOKEN_EXPIRE_MINUTES", "15")}
"""

    with io.open(PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(template)

    print("actions applied:")
    for action in actions:
        print(f"  - {action}")
    if not actions:
        print("  - none (provider flags already consistent)")
    print("file rewritten: single clean sectioned configuration, no duplicate keys")


if __name__ == "__main__":
    main()
