import streamlit as st
from datetime import datetime

from api.client import APIClient


def render(api: APIClient):
    st.title("🔔 Alerts Management")
    
    # =========================================================
    # FILTERS
    # =========================================================
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        severity_filter = st.selectbox(
            "Severity Filter",
            ["All", "Critical", "High", "Medium", "Low"],
            key="alert_severity_filter"
        )
    
    with col2:
        status_filter = st.selectbox(
            "Status Filter",
            ["All", "Pending", "Acknowledged", "Resolved"],
            key="alert_status_filter"
        )
    
    with col3:
        unresolved_only = st.checkbox("Unresolved Only", value=False, key="alert_unresolved")
    
    with col4:
        if st.button("🔄 Refresh Alerts", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # =========================================================
    # LOAD ALERTS
    # =========================================================
    
    with st.spinner("Loading alerts..."):
        resp = api.get("/alerts")
    
    if resp.status_code != 200:
        st.error("Failed to load alerts")
        st.info("Please check your connection and try again")
        return

    alerts_data = resp.json()
    alerts = alerts_data.get("items", []) if isinstance(alerts_data, dict) else alerts_data
    
    if not alerts:
        st.success("✅ No alerts - All systems are operational!")
        return
    
    # =========================================================
    # APPLY FILTERS
    # =========================================================
    
    filtered_alerts = alerts
    
    if severity_filter != "All":
        filtered_alerts = [a for a in filtered_alerts if a.get("severity", "").lower() == severity_filter.lower()]
    
    if status_filter != "All":
        filtered_alerts = [a for a in filtered_alerts if a.get("status", "").lower() == status_filter.lower()]
    
    if unresolved_only:
        filtered_alerts = [a for a in filtered_alerts if a.get("status") != "resolved"]
    
    if not filtered_alerts:
        st.info("No alerts match your current filters")
        return
    
    # =========================================================
    # ALERT SUMMARY
    # =========================================================
    
    st.markdown(f"### 📊 Alert Summary")
    
    total_alerts = len(alerts)
    critical_count = len([a for a in alerts if a.get("severity") == "critical"])
    high_count = len([a for a in alerts if a.get("severity") == "high"])
    pending_count = len([a for a in alerts if a.get("status") == "pending"])
    resolved_count = len([a for a in alerts if a.get("status") == "resolved"])
    
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total", total_alerts)
    c2.metric("🔴 Critical", critical_count)
    c3.metric("🟠 High", high_count)
    c4.metric("⏳ Pending", pending_count)
    c5.metric("✅ Resolved", resolved_count)
    
    st.divider()
    
    # =========================================================
    # ALERT LIST
    # =========================================================
    
    st.markdown(f"### 📋 Alert List ({len(filtered_alerts)} alerts)")
    
    for alert in filtered_alerts:
        # Extract alert data safely
        alert_id = alert.get("id", "unknown")
        severity = alert.get("severity", "unknown")
        status = alert.get("status", "unknown")
        server_name = alert.get("server_name", "Unknown Server")
        message = alert.get("message", "No message")
        metric_type = alert.get("metric_type", "Unknown")
        current_value = alert.get("current_value", 0)
        threshold = alert.get("threshold", 0)
        created_at = alert.get("created_at", "Unknown")
        
        # Severity styling
        severity_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
            "unknown": "⚪"
        }
        icon = severity_icons.get(str(severity).lower(), "⚪")
        
        severity_colors = {
            "critical": "#ff0000",
            "high": "#ff6600",
            "medium": "#ffcc00",
            "low": "#00ff00",
            "unknown": "#888888"
        }
        color = severity_colors.get(str(severity).lower(), "#888888")
        
        # Status styling
        status_colors = {
            "pending": "#ffcc00",
            "acknowledged": "#00ccff",
            "resolved": "#00ff00",
            "unknown": "#888888"
        }
        status_color = status_colors.get(str(status).lower(), "#888888")
        
        # Create alert card
        with st.expander(f"{icon} {server_name} - {message}", expanded=(severity == "critical")):
            # Alert details
            st.markdown(f"""
            <div style="
                background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1);
                border-left: 4px solid {color};
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 15px;
            ">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>Severity:</strong> {severity.upper()}<br>
                        <strong>Status:</strong> <span style="color: {status_color};">{status.upper()}</span><br>
                        <strong>Server:</strong> {server_name}<br>
                        <strong>Metric:</strong> {metric_type}<br>
                        <strong>Current Value:</strong> {current_value:.2f} / <strong>Threshold:</strong> {threshold:.2f}<br>
                        <strong>Created:</strong> {created_at}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if status == "pending":
                    if st.button("✅ Acknowledge", key=f"ack_{alert_id}", use_container_width=True):
                        response = api.put(f"/alerts/{alert_id}/acknowledge")
                        if response.status_code == 200:
                            st.success("Alert acknowledged!")
                            st.rerun()
                        else:
                            st.error("Failed to acknowledge alert")
            
            with col2:
                if status != "resolved":
                    if st.button("🔧 Resolve", key=f"res_{alert_id}", use_container_width=True):
                        response = api.put(f"/alerts/{alert_id}/resolve")
                        if response.status_code == 200:
                            st.success("Alert resolved!")
                            st.rerun()
                        else:
                            st.error("Failed to resolve alert")
            
            with col3:
                if status == "resolved":
                    if st.button("🔄 Reopen", key=f"reopen_{alert_id}", use_container_width=True):
                        response = api.put(f"/alerts/{alert_id}/reopen")
                        if response.status_code == 200:
                            st.success("Alert reopened!")
                            st.rerun()
                        else:
                            st.error("Failed to reopen alert")
            
            with col4:
                if st.button("📊 View Server", key=f"view_server_{alert_id}", use_container_width=True):
                    st.session_state.selected_server = alert.get("server_id")
                    st.session_state.page = "Server Detail"
                    st.rerun()
