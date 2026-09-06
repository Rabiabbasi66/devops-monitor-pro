import streamlit as st
from datetime import datetime

from api.client import APIClient


def render(api: APIClient):
    st.title("🔔 Notifications Center")
    
    # =========================================================
    # ACTIONS
    # =========================================================
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    with col2:
        if st.button("✅ Mark All Read", use_container_width=True):
            # Mark all as read (if backend supports it)
            st.info("Mark all as read feature coming soon")
    
    with col3:
        if st.button("🗑️ Clear All", use_container_width=True):
            # Clear all notifications (if backend supports it)
            st.info("Clear all feature coming soon")
    
    st.divider()
    
    # =========================================================
    # LOAD NOTIFICATIONS
    # =========================================================
    
    with st.spinner("Loading notifications..."):
        resp = api.get("/notifications")
    
    if resp.status_code != 200:
        st.error("Failed to load notifications")
        st.info("Please check your connection and try again")
        return

    data = resp.json()
    notifications = data.get("items", [])
    unread_count = data.get('unread', 0)
    
    # =========================================================
    # NOTIFICATION SUMMARY
    # =========================================================
    
    st.markdown("### 📊 Notification Summary")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", len(notifications))
    c2.metric("🔔 Unread", unread_count)
    c3.metric("✅ Read", len(notifications) - unread_count)
    
    st.divider()
    
    # =========================================================
    # NOTIFICATION LIST
    # =========================================================
    
    if not notifications:
        st.success("✅ No notifications - You're all caught up!")
        return
    
    st.markdown(f"### 📋 Notifications ({len(notifications)})")
    
    # Group notifications by read status
    unread_notifications = [n for n in notifications if not n.get("read", False)]
    read_notifications = [n for n in notifications if n.get("read", False)]
    
    # Display unread first
    if unread_notifications:
        st.markdown("#### 🔔 Unread Notifications")
        for notification in unread_notifications:
            display_notification(notification, api)
    
    if read_notifications:
        st.markdown("#### ✅ Read Notifications")
        for notification in read_notifications:
            display_notification(notification, api)


def display_notification(notification, api):
    """Display a single notification with actions."""
    notification_id = notification.get("id", "unknown")
    title = notification.get("title", "No Title")
    message = notification.get("message", "No message")
    notification_type = notification.get("type", "info")
    created_at = notification.get("created_at", "Unknown")
    is_read = notification.get("read", False)
    server_name = notification.get("server_name", None)
    
    # Type-based styling
    type_icons = {
        "alert": "🚨",
        "warning": "⚠️",
        "info": "ℹ️",
        "success": "✅",
        "error": "❌"
    }
    icon = type_icons.get(str(notification_type).lower(), "🔔")
    
    type_colors = {
        "alert": "#ff0000",
        "warning": "#ffcc00",
        "info": "#00ccff",
        "success": "#00ff00",
        "error": "#ff0000"
    }
    color = type_colors.get(str(notification_type).lower(), "#888888")
    
    # Create notification card
    with st.expander(f"{icon} {title}", expanded=not is_read):
        st.markdown(f"""
        <div style="
            background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1);
            border-left: 4px solid {color};
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
        ">
            <strong>Type:</strong> {notification_type.upper()}<br>
            <strong>Message:</strong> {message}<br>
            <strong>Time:</strong> {created_at}
            {f"<br><strong>Server:</strong> {server_name}" if server_name else ""}
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if not is_read:
                if st.button("✅ Mark as Read", key=f"read_{notification_id}", use_container_width=True):
                    response = api.put(f"/notifications/{notification_id}/read")
                    if response.status_code == 200:
                        st.success("Marked as read!")
                        st.rerun()
                    else:
                        st.error("Failed to mark as read")
        
        with col2:
            if server_name:
                if st.button("📊 View Server", key=f"notif_server_{notification_id}", use_container_width=True):
                    # Extract server ID if available
                    server_id = notification.get("server_id")
                    if server_id:
                        st.session_state.selected_server = server_id
                        st.session_state.page = "Server Detail"
                        st.rerun()
