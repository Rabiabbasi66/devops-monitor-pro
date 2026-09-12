import pandas as pd
import streamlit as st

from api.client import APIClient

PROVIDER_LABELS = {
    "email": "📧 Email",
    "whatsapp": "💬 WhatsApp",
    "telegram": "✈️ Telegram",
}
SEVERITIES = ["info", "warning", "high", "critical"]
NOTIFICATION_TYPES = ["alert", "recovery", "offline", "security"]
PLATFORM_UNAVAILABLE = "**Platform configuration unavailable.** Contact administrator."


def render(api: APIClient):
    st.title("⚙️ Settings")
    user = st.session_state.get("user", {})

    # Profile Section
    st.header("👤 Profile")
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Email:** {user.get('email')}")
    st.write(f"**Role:** {user.get('role')}")

    st.markdown("---")

    render_notification_channels(api)

    st.markdown("---")

    # Admin Section
    if user.get("role") == "admin":
        st.header("🔧 Admin")

        st.subheader("Audit Logs")
        resp = api.get("/audit-logs")
        if resp.status_code == 200:
            logs = resp.json().get("items", [])
            if logs:
                st.dataframe(pd.DataFrame(logs), use_container_width=True)
            else:
                st.info("No audit logs yet.")
        else:
            st.error("Unable to load audit logs")

        st.subheader("Users")
        users_resp = api.get("/admin/users")
        if users_resp.status_code == 200:
            st.dataframe(pd.DataFrame(users_resp.json()), use_container_width=True)


# =========================================================================
# Notification Channels (multi-tenant SaaS architecture)
#
# Platform provider credentials (SMTP, WhatsApp sender, Telegram bot) are
# managed by the platform administrator via environment configuration.
# Clients only connect their own recipient destination. No credential
# fields (Phone Number ID, Access Token, Bot Token, SMTP password) are
# ever shown here.
# =========================================================================


def _load_provider_status(api: APIClient) -> dict:
    """Fetch platform provider availability (booleans only, no secrets)."""
    resp = api.get("/notifications/settings/providers/status")
    if resp.status_code == 200:
        return resp.json().get("providers", {})
    return {}


def render_notification_channels(api: APIClient):
    st.header("🔔 Notification Channels")
    st.markdown(
        "Choose where alerts are delivered. Provider infrastructure is managed "
        "by the platform administrator — you only connect your own recipient."
    )

    status = _load_provider_status(api)

    channels_resp = api.get("/notifications/settings")
    channels = channels_resp.json() if channels_resp.status_code == 200 else []
    by_provider = {c.get("provider"): c for c in channels}

    for provider in ["email", "whatsapp", "telegram"]:
        _render_provider_card(api, provider, by_provider.get(provider), status.get(provider, {}))


def _render_provider_card(api, provider, channel, provider_status):
    label = PROVIDER_LABELS.get(provider, provider)
    st.subheader(label)

    if not provider_status.get("available", False):
        st.info(PLATFORM_UNAVAILABLE)
        return

    if channel:
        connected = "Connected ✓" if channel.get("enabled") else "Disabled"
        st.success(f"{connected}  |  `{channel.get('recipient', '')}`")
        _render_connected_actions(api, provider, channel)
    else:
        st.warning("Not connected")
        if provider == "telegram":
            _render_telegram_connect(api)
        else:
            _render_configure_form(api, provider, None)


def _render_connected_actions(api, provider, channel):
    has_disconnect = provider in ("whatsapp", "telegram")
    columns = st.columns(3) if has_disconnect else st.columns(2)

    with columns[0]:
        if st.button("🧪 Test", key=f"test_{provider}", use_container_width=True):
            resp = api.post(
                "/notifications/settings/test",
                json={"provider": provider, "recipient": channel.get("recipient")},
            )
            _show_test_result(resp)

    with columns[1]:
        if st.button("⚙️ Configure", key=f"cfg_{provider}", use_container_width=True):
            st.session_state[f"configure_{provider}"] = not st.session_state.get(
                f"configure_{provider}", False
            )

    if has_disconnect:
        with columns[2]:
            if st.button("🔌 Disconnect", key=f"disc_{provider}", use_container_width=True):
                if provider == "telegram":
                    resp = api.delete("/notifications/settings/telegram/disconnect")
                else:
                    resp = api.delete(f"/notifications/settings/{channel['id']}")
                if resp.status_code == 200:
                    st.success("Disconnected")
                    st.rerun()
                else:
                    st.error("Failed to disconnect")

    if st.session_state.get(f"configure_{provider}", False):
        _render_configure_form(api, provider, channel)


def _show_test_result(resp):
    if resp.status_code != 200:
        st.error("❌ Failed to send test notification")
        return
    try:
        data = resp.json()
    except Exception:
        data = {}
    if data.get("success"):
        st.success("✅ Test notification sent successfully!")
    else:
        details = data.get("details", {})
        st.error(f"❌ Test failed: {details.get('error', 'Unknown error')}")

def _render_configure_form(api, provider, channel):
    is_update = channel is not None
    with st.expander("Channel settings", expanded=True):
        if provider == "telegram" and not is_update:
            st.info("Use **Connect Telegram** — no manual chat ID entry needed.")
            recipient = ""
        else:
            placeholder = {"email": "you@example.com", "whatsapp": "+92 300 1234567"}.get(provider, "")
            recipient = st.text_input(
                "Recipient",
                value=(channel.get("recipient", "") if is_update else ""),
                placeholder=placeholder,
                key=f"recipient_{provider}",
                help="Email for Email; international phone number (E.164) for WhatsApp.",
            )

        default_severity = channel.get("min_severity", "warning") if is_update else "warning"
        min_severity = st.selectbox(
            "Minimum severity",
            SEVERITIES,
            index=SEVERITIES.index(default_severity) if default_severity in SEVERITIES else 1,
            key=f"severity_{provider}",
            help="Only send notifications of this severity or higher",
        )

        default_types = (
            channel.get("notification_types", ["alert", "recovery", "offline"])
            if is_update
            else ["alert", "recovery", "offline"]
        )
        notification_types = st.multiselect(
            "Notification types",
            NOTIFICATION_TYPES,
            default=[t for t in default_types if t in NOTIFICATION_TYPES],
            key=f"types_{provider}",
            help="Which types of notifications to send through this channel",
        )

        cooldown_seconds = st.slider(
            "Cooldown (seconds)",
            min_value=0,
            max_value=3600,
            value=(channel.get("cooldown_seconds", 300) if is_update else 300),
            step=60,
            key=f"cooldown_{provider}",
            help="Minimum time between notifications through this channel",
        )

        enabled = st.checkbox(
            "Enable channel",
            value=(channel.get("enabled", True) if is_update else True),
            key=f"enabled_{provider}",
        )

        if st.button("💾 Save", key=f"save_{provider}", use_container_width=True):
            if provider != "telegram" and not recipient:
                st.error("❌ Please enter a recipient")
                return
            payload = {
                "provider": provider,
                "enabled": enabled,
                "recipient": recipient,
                "min_severity": min_severity,
                "notification_types": notification_types,
                "cooldown_seconds": cooldown_seconds,
            }
            if is_update:
                resp = api.put(f"/notifications/settings/{channel['id']}", json=payload)
            else:
                resp = api.post("/notifications/settings", json=payload)
            if resp.status_code == 200:
                st.success("✅ Notification channel saved!")
                st.session_state[f"configure_{provider}"] = False
                st.rerun()
            else:
                try:
                    detail = resp.json().get("detail", "")
                except Exception:
                    detail = ""
                st.error(f"❌ Failed to save channel: {detail or 'Unknown error'}")


def _render_telegram_connect(api: APIClient):
    """One-time token flow for the platform-managed Telegram bot."""
    if st.button("🔗 Connect Telegram", key="tg_connect", use_container_width=True):
        resp = api.post("/notifications/settings/telegram/connect")
        if resp.status_code == 200:
            data = resp.json()
            st.session_state["tg_token"] = data.get("token")
            st.session_state["tg_url"] = data.get("connect_url")
            st.session_state["tg_bot"] = data.get("bot_username")
        else:
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = ""
            st.error(detail or "Could not start Telegram connection")

    token = st.session_state.get("tg_token")
    if not token:
        return

    url = st.session_state.get("tg_url")
    bot = st.session_state.get("tg_bot")
    st.markdown("#### Finish connecting Telegram")
    bot_label = f"[@{bot}](https://t.me/{bot})" if bot else "the platform bot"
    st.markdown(
        f"1. Open the platform bot: {bot_label}\n"
        "2. Send **/start** to it (the link below includes your one-time "
        "connection token automatically)\n"
        "3. Click **Check status**"
    )
    if url:
        st.markdown(f"[Open bot and connect]({url})")
    st.code(f"/start {token}", language=None)

    if st.button("✅ Check status", key="tg_check", use_container_width=True):
        resp = api.get("/notifications/settings/telegram/connect/status", token=token)
        if resp.status_code == 200 and resp.json().get("connected"):
            st.success("Telegram connected!")
            st.session_state.pop("tg_token", None)
            st.session_state.pop("tg_url", None)
            st.rerun()
        elif resp.status_code == 200:
            status_data = resp.json()
            if status_data.get("expired"):
                st.warning("Connection token expired — click Connect Telegram again.")
            else:
                st.info("Not connected yet — send /start to the bot, then check again.")
        else:
            st.error("Failed to check connection status")
