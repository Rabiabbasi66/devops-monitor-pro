import pandas as pd
import streamlit as st

from api.client import APIClient


def render(api: APIClient):
    st.title("⚙️ Settings")
    user = st.session_state.get("user", {})
    
    # Profile Section
    st.header("👤 Profile")
    st.write(f"**Username:** {user.get('username')}")
    st.write(f"**Email:** {user.get('email')}")
    st.write(f"**Role:** {user.get('role')}")
    
    st.markdown("---")
    
    # Notification Settings Section
    st.header("🔔 Notification Channels")
    st.markdown("Configure how you want to receive alerts and notifications.")
    
    # Load existing notification channels
    channels_resp = api.get("/notifications/settings")
    channels = []
    if channels_resp.status_code == 200:
        channels = channels_resp.json()
    
    # Display existing channels
    if channels:
        st.subheader("Configured Channels")
        for channel in channels:
            with st.expander(f"{channel['provider'].upper()} - {channel['recipient']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                col1.metric("Status", "✅ Enabled" if channel['enabled'] else "❌ Disabled")
                col2.metric("Min Severity", channel['min_severity'].upper())
                col3.metric("Cooldown", f"{channel['cooldown_seconds']}s")
                
                st.write("**Notification Types:**", ", ".join(channel['notification_types']))
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"Test {channel['provider']}", key=f"test_{channel['id']}"):
                        test_resp = api.post("/notifications/settings/test", json={
                            "provider": channel['provider'],
                            "recipient": channel['recipient']
                        })
                        if test_resp.status_code == 200:
                            st.success("✅ Test notification sent successfully!")
                        else:
                            st.error("❌ Failed to send test notification")
                
                with col2:
                    if st.button(f"Delete {channel['provider']}", key=f"delete_{channel['id']}"):
                        delete_resp = api.delete(f"/notifications/settings/{channel['id']}")
                        if delete_resp.status_code == 200:
                            st.success("Channel deleted successfully")
                            st.rerun()
                        else:
                            st.error("Failed to delete channel")
    else:
        st.info("No notification channels configured yet.")
    
    st.markdown("---")
    
    # Add new notification channel
    st.subheader("Add Notification Channel")
    
    provider = st.selectbox(
        "Provider",
        ["email", "whatsapp", "telegram"],
        format_func=lambda x: x.upper(),
        key="new_provider"
    )
    
    recipient = st.text_input(
        "Recipient",
        placeholder="Email address, phone number, or chat ID",
        key="new_recipient",
        help="Email for Email provider, phone number for WhatsApp, chat ID for Telegram"
    )
    
    enabled = st.checkbox("Enable this channel", value=True, key="new_enabled")
    
    min_severity = st.selectbox(
        "Minimum Severity",
        ["info", "warning", "high", "critical"],
        index=1,
        key="new_min_severity",
        help="Only send notifications of this severity or higher"
    )
    
    notification_types = st.multiselect(
        "Notification Types",
        ["alert", "recovery", "offline", "security"],
        default=["alert", "recovery", "offline"],
        key="new_types",
        help="Which types of notifications to send through this channel"
    )
    
    cooldown_seconds = st.slider(
        "Cooldown (seconds)",
        min_value=60,
        max_value=3600,
        value=300,
        step=60,
        key="new_cooldown",
        help="Minimum time between notifications of the same type"
    )
    
    if st.button("Add Channel", use_container_width=True):
        if not recipient:
            st.error("❌ Please enter a recipient")
        else:
            create_resp = api.post("/notifications/settings", json={
                "provider": provider,
                "enabled": enabled,
                "recipient": recipient,
                "min_severity": min_severity,
                "notification_types": notification_types,
                "cooldown_seconds": cooldown_seconds
            })
            if create_resp.status_code == 200:
                st.success("✅ Notification channel added successfully!")
                st.rerun()
            else:
                st.error("❌ Failed to add notification channel")
    
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
