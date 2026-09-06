import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime

from api.client import APIClient


def render(api: APIClient):
    server_id = st.session_state.get("selected_server")
    if not server_id:
        st.warning("Select a server from the Servers page.")
        return

    # Load server data with loading state
    with st.spinner("Loading server details..."):
        resp = api.get(f"/servers/{server_id}")
    
    if resp.status_code != 200:
        st.error("Server not found or access denied")
        st.info("Please select a valid server from the Servers page")
        return
    
    server = resp.json()

    # =========================================================
    # SERVER HEADER
    # =========================================================
    
    st.title(f"📊 {server['name']}")
    
    # Status indicator
    status = server.get("status", "unknown")
    health = server.get("health_status", "unknown")
    
    status_colors = {
        "running": "#00ff00",
        "stopped": "#ff0000",
        "error": "#ff0000",
        "unknown": "#888888"
    }
    
    health_colors = {
        "healthy": "#00ff00",
        "warning": "#ffaa00",
        "critical": "#ff0000",
        "offline": "#666666",
        "unknown": "#888888"
    }
    
    status_color = status_colors.get(str(status).lower(), "#888888")
    health_color = health_colors.get(str(health).lower(), "#888888")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Status",
            status.upper(),
            delta=None,
            help="Current server status"
        )
    
    with col2:
        st.metric(
            "Health",
            health.upper(),
            delta=None,
            help="Server health status based on metrics"
        )
    
    with col3:
        uptime = server.get('uptime', 0)
        if uptime > 86400:  # More than 1 day
            uptime_str = f"{uptime/86400:.1f}d"
        elif uptime > 3600:  # More than 1 hour
            uptime_str = f"{uptime/3600:.1f}h"
        else:
            uptime_str = f"{uptime:.0f}s"
        st.metric("Uptime", uptime_str, delta=None)
    
    with col4:
        cpu = server.get('cpu_usage', 0)
        st.metric("CPU", f"{cpu:.1f}%", delta=None)
    
    with col5:
        memory = server.get('memory_usage', 0)
        st.metric("Memory", f"{memory:.1f}%", delta=None)

    # Server information
    st.markdown("### ℹ️ Server Information")
    
    info_col1, info_col2, info_col3 = st.columns(3)
    
    with info_col1:
        st.info(f"**IP Address:** {server['ip_address']}")
        st.info(f"**Server Type:** {server.get('server_type', 'N/A')}")
    
    with info_col2:
        st.info(f"**Hostname:** {server.get('hostname', 'N/A')}")
        st.info(f"**OS:** {server.get('operating_system', 'N/A')}")
    
    with info_col3:
        last_seen = server.get('last_seen')
        if last_seen:
            try:
                last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                last_seen_str = last_seen_dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                last_seen_str = str(last_seen)
        else:
            last_seen_str = "Never"
        st.info(f"**Last Seen:** {last_seen_str}")
        st.info(f"**Response Time:** {server.get('response_time_ms', 'N/A')} ms")

    st.divider()

    # =========================================================
    # METRICS CHARTS WITH TIME RANGES
    # =========================================================
    
    st.markdown("### 📈 Metrics History")
    
    # Time range selector
    time_range = st.selectbox(
        "Select Time Range",
        ["1 Hour", "6 Hours", "12 Hours", "24 Hours", "48 Hours", "72 Hours"],
        index=3,
        horizontal=True
    )
    
    hours_map = {
        "1 Hour": 1,
        "6 Hours": 6,
        "12 Hours": 12,
        "24 Hours": 24,
        "48 Hours": 48,
        "72 Hours": 72
    }
    
    hours = hours_map[time_range]
    
    # Auto-refresh option
    auto_refresh = st.checkbox("🔄 Auto-refresh metrics (30s)", value=False)
    if auto_refresh:
        import time
        if 'last_metrics_refresh' not in st.session_state:
            st.session_state.last_metrics_refresh = time.time()
        
        if time.time() - st.session_state.last_metrics_refresh > 30:
            st.session_state.last_metrics_refresh = time.time()
            st.rerun()
    
    # Load metrics
    with st.spinner("Loading metrics..."):
        metrics_resp = api.get(f"/servers/{server_id}/metrics", hours=hours, limit=1000)
    
    if metrics_resp.status_code != 200:
        st.info("No metrics available for this time range.")
        st.info("Ensure the monitoring agent is running and sending data.")
        return

    items = metrics_resp.json().get("items", [])
    if not items:
        st.info("No metrics collected yet for this time range.")
        st.info("Start the monitoring agent to begin data collection.")
        return

    # Process metrics data
    df = pd.DataFrame(items)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")
    
    # Create advanced charts
    fig = make_subplots(
        rows=3, cols=2,
        subplot_titles=("CPU Usage (%)", "Memory Usage (%)", "Disk Usage (%)", "Network Activity", "Response Time", "Process Count"),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "scatter"}, {"type": "scatter"}]]
    )
    
    # CPU
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["cpu_usage"],
            name="CPU",
            mode='lines',
            line=dict(color='#3b82f6', width=2),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)'
        ),
        row=1, col=1
    )
    
    # Memory
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["memory_usage"],
            name="Memory",
            mode='lines',
            line=dict(color='#10b981', width=2),
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.1)'
        ),
        row=1, col=2
    )
    
    # Disk
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["disk_usage"],
            name="Disk",
            mode='lines',
            line=dict(color='#f59e0b', width=2),
            fill='tozeroy',
            fillcolor='rgba(245, 158, 11, 0.1)'
        ),
        row=2, col=1
    )
    
    # Network
    if "network_received" in df.columns and "network_sent" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["network_received"],
                name="Network RX",
                mode='lines',
                line=dict(color='#8b5cf6', width=2)
            ),
            row=2, col=2
        )
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["network_sent"],
                name="Network TX",
                mode='lines',
                line=dict(color='#ec4899', width=2)
            ),
            row=2, col=2
        )
    
    # Response time (if available)
    if "response_time_ms" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["response_time_ms"],
                name="Response Time",
                mode='lines',
                line=dict(color='#06b6d4', width=2)
            ),
            row=3, col=1
        )
    
    # Process count (if available)
    if "process_count" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["timestamp"],
                y=df["process_count"],
                name="Process Count",
                mode='lines',
                line=dict(color='#f97316', width=2)
            ),
            row=3, col=2
        )
    
    # Update layout
    fig.update_layout(
        height=900,
        showlegend=True,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        hovermode='x unified'
    )
    
    fig.update_xaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)', color='white')
    fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)', color='white')
    
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # =========================================================
    # THRESHOLD SETTINGS
    # =========================================================
    
    st.markdown("### ⚙️ Alert Thresholds")
    
    thresholds = server.get("thresholds", {})
    
    with st.form("thresholds"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### CPU Thresholds")
            cpu_w = st.number_input(
                "CPU Warning (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("cpu_warning", 80.0)),
                step=1.0
            )
            cpu_c = st.number_input(
                "CPU Critical (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("cpu_critical", 95.0)),
                step=1.0
            )
        
        with col2:
            st.markdown("#### Memory Thresholds")
            mem_w = st.number_input(
                "Memory Warning (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("memory_warning", 85.0)),
                step=1.0
            )
            mem_c = st.number_input(
                "Memory Critical (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("memory_critical", 95.0)),
                step=1.0
            )
        
        with col3:
            st.markdown("#### Disk Thresholds")
            disk_w = st.number_input(
                "Disk Warning (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("disk_warning", 85.0)),
                step=1.0
            )
            disk_c = st.number_input(
                "Disk Critical (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(thresholds.get("disk_critical", 90.0)),
                step=1.0
            )
        
        if st.form_submit_button("💾 Save Thresholds", use_container_width=True):
            response = api.put(
                f"/servers/{server_id}/thresholds",
                json={
                    "thresholds": {
                        "cpu_warning": cpu_w,
                        "cpu_critical": cpu_c,
                        "memory_warning": mem_w,
                        "memory_critical": mem_c,
                        "disk_warning": disk_w,
                        "disk_critical": disk_c,
                    }
                },
            )
            if response.status_code == 200:
                st.success("✅ Thresholds updated successfully!")
                st.rerun()
            else:
                st.error("Failed to update thresholds")

    st.divider()

    # =========================================================
    # ALERT HISTORY
    # =========================================================
    
    st.markdown("### 🔔 Alert History")
    
    alerts_resp = api.get("/alerts")
    if alerts_resp.status_code == 200:
        alerts_data = alerts_resp.json()
        alerts = alerts_data.get("items", []) if isinstance(alerts_data, dict) else alerts_data
        server_alerts = [a for a in alerts if a.get("server_id") == server_id]
        
        if not server_alerts:
            st.success("✅ No alerts for this server - Everything is running smoothly!")
        else:
            # Display alerts in a nice format
            for alert in server_alerts:
                sev = alert.get("severity", "unknown")
                message = alert.get("message", "No message")
                created_at = alert.get("created_at", "Unknown")
                status = alert.get("status", "unknown")
                
                severity_colors = {
                    "critical": "#ff0000",
                    "high": "#ff6600",
                    "medium": "#ffcc00",
                    "low": "#00ff00",
                    "unknown": "#888888"
                }
                color = severity_colors.get(str(sev).lower(), "#888888")
                
                st.markdown(f"""
                <div style="
                    background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1);
                    border-left: 4px solid {color};
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 10px;
                ">
                    <strong>Severity:</strong> {sev.upper()}<br>
                    <strong>Status:</strong> {status.upper()}<br>
                    <strong>Message:</strong> {message}<br>
                    <strong>Time:</strong> {created_at}
                </div>
                """, unsafe_allow_html=True)

    # Back button
    if st.button("← Back to Servers", use_container_width=True):
        st.session_state.page = "Servers"
        st.rerun()
