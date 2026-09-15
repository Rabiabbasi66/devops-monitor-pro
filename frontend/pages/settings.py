import streamlit as st

from api.client import APIClient

SEVERITIES = ["info", "warning", "high", "critical"]
NOTIFICATION_TYPES = ["alert", "recovery", "offline"]


def render(api: APIClient):
    st.title("⚙️ Settings")
    user = st.session_state.get("user")
    if not user:
        # Session state can lose the cached profile; refresh it from the
        # backend via the canonical current-user endpoint (GET {API_URL}/auth/me),
        # which always resolves to the configured production API base.
        api.get_user_details()
        user = st.session_state.get("user") or {}

    # Profile Section
    st.header("👤 Profile")
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Email:** {user.get('email')}")
    st.write(f"**Role:** {user.get('role')}")

    st.markdown("---")

    render_email_notifications(api)

    st.markdown("---")

    # Admin Section
    if user.get("role") == "admin":
        st.header("🔧 Admin")

        st.subheader("Audit Logs")
        resp = api.get("/audit-logs")
        if resp.status_code == 200:
            logs = resp.json().get("items", [])
            if logs:
                st.dataframe(logs, use_container_width=True)
            else:
                st.info("No audit logs yet.")
        else:
            st.error("Unable to load audit logs")

        st.subheader("Users")
        users_resp = api.get("/admin/users")
        if users_resp.status_code == 200:
            st.dataframe(users_resp.json(), use_container_width=True)


def render_email_notifications(api: APIClient):
    st.header("🔔 Email Notifications")
    st.markdown(
        "Configure email notifications for alerts. SMTP credentials are managed "
        "securely by the platform — you only provide your email address."
    )

    # Check if email is already configured
    channels_resp = api.get("/notifications/settings")
    channels = channels_resp.json() if channels_resp.status_code == 200 else []
    email_channel = next((c for c in channels if c.get("provider") == "email"), None)

    if email_channel and email_channel.get("enabled"):
        st.success(f"✅ Email verified: `{email_channel.get('recipient', '')}`")
        _render_email_configuration(api, email_channel)
    else:
        st.warning("Email not verified")
        _render_email_verification(api)


def _render_email_verification(api: APIClient):
    with st.expander("Verify Email", expanded=True):
        email = st.text_input(
            "Email address",
            placeholder="you@example.com",
            key="email_verify_input",
            help="Enter your email address to receive a verification code"
        )

        if st.button("📧 Send verification code", key="send_verify", use_container_width=True):
            if not email:
                st.error("❌ Please enter an email address")
                return

            resp = api.post("/notifications/settings/email/request-verification", json={"email": email})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success"):
                    st.success("✅ Verification code sent! Check your email.")
                    st.session_state["verify_email"] = email
                else:
                    st.error(f"❌ {data.get('error', 'Failed to send verification code')}")
            else:
                st.error("❌ Failed to request verification code")

        if st.session_state.get("verify_email"):
            st.markdown("#### Enter verification code")
            code = st.text_input(
                "Verification code",
                placeholder="123456",
                key="verify_code_input",
                max_chars=6,
                help="Enter the 6-digit code from your email"
            )

            if st.button("✅ Verify Email", key="verify_email_btn", use_container_width=True):
                if not code or len(code) != 6:
                    st.error("❌ Please enter a valid 6-digit code")
                    return

                resp = api.post(
                    "/notifications/settings/email/verify",
                    json={"email": st.session_state["verify_email"], "code": code}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        st.success("✅ Email verified successfully!")
                        st.balloons()
                        st.session_state.pop("verify_email", None)
                        st.rerun()
                    else:
                        st.error(f"❌ {data.get('error', 'Verification failed')}")
                else:
                    st.error("❌ Verification failed")


def _render_email_configuration(api: APIClient, channel):
    st.markdown("#### Email Settings")

    with st.expander("Channel settings", expanded=True):
        default_severity = channel.get("min_severity", "warning")
        min_severity = st.selectbox(
            "Minimum severity",
            SEVERITIES,
            index=SEVERITIES.index(default_severity) if default_severity in SEVERITIES else 1,
            key="email_severity",
            help="Only send notifications of this severity or higher"
        )

        default_types = channel.get("notification_types", ["alert", "recovery", "offline"])
        notification_types = st.multiselect(
            "Notification types",
            NOTIFICATION_TYPES,
            default=[t for t in default_types if t in NOTIFICATION_TYPES],
            key="email_types",
            help="Which types of notifications to send"
        )

        cooldown_seconds = st.slider(
            "Cooldown (seconds)",
            min_value=0,
            max_value=3600,
            value=channel.get("cooldown_seconds", 300),
            step=60,
            key="email_cooldown",
            help="Minimum time between notifications"
        )

        enabled = st.checkbox(
            "Enable notifications",
            value=channel.get("enabled", True),
            key="email_enabled"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save", key="save_email", use_container_width=True):
                payload = {
                    "provider": "email",
                    "enabled": enabled,
                    "recipient": channel.get("recipient"),
                    "min_severity": min_severity,
                    "notification_types": notification_types,
                    "cooldown_seconds": cooldown_seconds,
                }
                resp = api.put(f"/notifications/settings/{channel['id']}", json=payload)
                if resp.status_code == 200:
                    st.success("✅ Settings saved!")
                else:
                    st.error("❌ Failed to save settings")

        with col2:
            if st.button("🧪 Test Email", key="test_email", use_container_width=True):
                resp = api.post(
                    "/notifications/settings/test",
                    json={"provider": "email", "recipient": channel.get("recipient")}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        st.success("✅ Test email sent successfully!")
                    else:
                        st.error(f"❌ Test failed: {data.get('details', {}).get('error', 'Unknown error')}")
                else:
                    st.error("❌ Failed to send test email")

        if st.button("🔌 Disable", key="disable_email", use_container_width=True):
            payload = {"enabled": False}
            resp = api.put(f"/notifications/settings/{channel['id']}", json=payload)
            if resp.status_code == 200:
                st.success("✅ Email notifications disabled")
                st.rerun()
            else:
                st.error("❌ Failed to disable")
