import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from datetime import datetime, timedelta

from api.client import APIClient


def render(api: APIClient):
    st.title("📊 DevOps Monitor Pro Dashboard")
    
    # Auto-refresh option
    auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", value=False)
    if auto_refresh:
        st_autorefresh(interval=30000, key="dashboard_refresh")
    
    # Load dashboard summary
    with st.spinner("Loading dashboard data..."):
        response = api.get("/dashboard/summary")
    
    if response.status_code != 200:
        st.error("Unable to load dashboard data. Please check your connection.")
        st.info("🔍 Troubleshooting:")
        st.info("- Ensure the backend is running")
        st.info("- Check your authentication status")
        st.info("- Verify API URL configuration")
        return

    stats = response.json()
    
    # Empty state
    if stats["total_servers"] == 0:
        st.info("🚀 No servers yet. Add a server to start monitoring.")
        st.info("1. Go to the Servers page")
        st.info("2. Click 'Add Server'")
        st.info("3. Install the monitoring agent")
        return

    # =========================================================
    # TOP SUMMARY METRICS
    # =========================================================
    
    st.markdown("### 📈 Overview")
    
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        st.metric(
            "Total Servers", 
            stats["total_servers"],
            delta=None,
            help="Total number of registered servers"
        )
    
    with c2:
        st.metric(
            "🟢 Online", 
            stats["online_servers"],
            delta=None,
            help="Servers currently online and responding"
        )
    
    with c3:
        st.metric(
            "🟡 Warning", 
            stats.get("warning_servers", 0),
            delta=None,
            help="Servers with warning level health status"
        )
    
    with c4:
        st.metric(
            "🔴 Critical", 
            stats["critical_servers"],
            delta=None,
            help="Servers with critical level health status"
        )
    
    with c5:
        st.metric(
            "⚫ Offline", 
            stats["offline_servers"],
            delta=None,
            help="Servers currently offline"
        )
    
    with c6:
        st.metric(
            "🔔 Active Alerts", 
            stats["pending_alerts"],
            delta=None,
            help="Number of unresolved alerts"
        )

    # Additional metrics row
    c7, c8, c9 = st.columns(3)
    
    with c7:
        uptime_pct = stats.get('uptime_percentage', 0)
        st.metric(
            "⏱️ Uptime %", 
            f"{uptime_pct:.1f}%",
            delta=None,
            help="Overall server uptime percentage"
        )
    
    with c8:
        st.metric(
            "💾 Avg Memory", 
            f"{stats.get('avg_memory', 0):.1f}%",
            delta=None,
            help="Average memory usage across all servers"
        )
    
    with c9:
        st.metric(
            "🖥️ Avg CPU", 
            f"{stats.get('avg_cpu', 0):.1f}%",
            delta=None,
            help="Average CPU usage across all servers"
        )

    st.divider()

    # =========================================================
    # SERVER OVERVIEW TABLE
    # =========================================================
    
    st.markdown("### 🖥️ Server Overview")
    
    servers_resp = api.get("/servers")
    servers = servers_resp.json() if servers_resp.status_code == 200 else []
    
    if not servers:
        st.warning("No servers data available")
        return
    
    # Create DataFrame for better display
    server_data = []
    for server in servers:
        server_data.append({
            "Name": server.get("name", "Unknown"),
            "Status": server.get("status", "unknown"),
            "Health": server.get("health_status", "unknown"),
            "CPU": f"{server.get('cpu_usage', 0):.1f}%",
            "Memory": f"{server.get('memory_usage', 0):.1f}%",
            "Disk": f"{server.get('disk_usage', 0):.1f}%",
            "Uptime": f"{server.get('uptime', 0) / 3600:.1f}h" if server.get('uptime') else "N/A",
            "Last Seen": server.get('last_seen', 'N/A')[:19] if server.get('last_seen') else 'N/A',
        })
    
    df = pd.DataFrame(server_data)
    
    # Health status styling (pandas 2.x: use .map, not deprecated .applymap)
    def highlight_health(val):
        if val == "healthy":
            return 'background-color: rgba(0, 255, 0, 0.2)'
        elif val == "warning":
            return 'background-color: rgba(255, 165, 0, 0.2)'
        elif val == "critical":
            return 'background-color: rgba(255, 0, 0, 0.2)'
        elif val == "offline":
            return 'background-color: rgba(128, 128, 128, 0.2)'
        return ''

    styled_df = df.style.map(highlight_health, subset=['Health'])
    st.dataframe(styled_df, use_container_width=True, height=300)
    
    st.divider()

    # =========================================================
    # RESOURCE USAGE CHARTS
    # =========================================================
    
    st.markdown("### 📊 Resource Usage")
    
    if servers:
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=("CPU Usage", "Memory Usage", "Disk Usage", "Network Activity"),
            specs=[[{"type": "bar"}, {"type": "bar"}],
                   [{"type": "bar"}, {"type": "scatter"}]]
        )
        
        names = [s["name"] for s in servers]
        
        # CPU
        fig.add_trace(
            go.Bar(
                x=names,
                y=[s.get("cpu_usage", 0) for s in servers],
                name="CPU",
                marker_color="#3b82f6",
                text=[f"{s.get('cpu_usage', 0):.1f}%" for s in servers],
                textposition='auto'
            ),
            row=1, col=1
        )
        
        # Memory
        fig.add_trace(
            go.Bar(
                x=names,
                y=[s.get("memory_usage", 0) for s in servers],
                name="Memory",
                marker_color="#10b981",
                text=[f"{s.get('memory_usage', 0):.1f}%" for s in servers],
                textposition='auto'
            ),
            row=1, col=2
        )
        
        # Disk
        fig.add_trace(
            go.Bar(
                x=names,
                y=[s.get("disk_usage", 0) for s in servers],
                name="Disk",
                marker_color="#f59e0b",
                text=[f"{s.get('disk_usage', 0):.1f}%" for s in servers],
                textposition='auto'
            ),
            row=2, col=1
        )
        
        # Network received (bytes since boot — cumulative counter, shown as-is)
        net_rx = [s.get("network_received", None) for s in servers]
        # Only show if at least one server has non-zero network data
        if any(v and v > 0 for v in net_rx):
            fig.add_trace(
                go.Bar(
                    x=names,
                    y=[v or 0 for v in net_rx],
                    name="Net RX (bytes)",
                    marker_color="#8b5cf6",
                    text=[f"{(v or 0)/1e6:.0f}MB" for v in net_rx],
                    textposition='auto'
                ),
                row=2, col=2
            )
        else:
            # Placeholder when network data not yet available
            fig.add_trace(
                go.Scatter(
                    x=names,
                    y=[0] * len(servers),
                    name="Network (pending)",
                    mode='markers',
                    marker_color="#8b5cf6"
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            height=600,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
        
        fig.update_xaxes(showgrid=False, color='white')
        fig.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)', color='white')
        
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # =========================================================
    # ACTIVE ALERTS
    # =========================================================
    
    st.markdown("### 🔔 Active Alerts")
    
    alerts_resp = api.get("/alerts/pending")
    if alerts_resp.status_code == 200:
        alerts_data = alerts_resp.json()
        alerts = alerts_data.get("items", []) if isinstance(alerts_data, dict) else alerts_data
        
        if not alerts:
            st.success("✅ No active alerts - All systems operational!")
        else:
            for alert in alerts:
                sev = alert.get("severity", "unknown")
                server_name = alert.get("server_name", "Unknown Server")
                message = alert.get("message", "No message")
                alert_id = alert.get("id")
                
                # Severity styling
                severity_icons = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                    "unknown": "⚪"
                }
                icon = severity_icons.get(str(sev).lower(), "⚪")
                
                severity_colors = {
                    "critical": "#ff0000",
                    "high": "#ff6600",
                    "medium": "#ffcc00",
                    "low": "#00ff00",
                    "unknown": "#888888"
                }
                color = severity_colors.get(str(sev).lower(), "#888888")
                
                with st.expander(f"{icon} {server_name} - {message}", expanded=False):
                    st.markdown(f"""
                    <div style="padding: 10px; background: rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.1); border-radius: 5px; border-left: 3px solid {color};">
                        <strong>Severity:</strong> {sev.upper()}<br>
                        <strong>Server:</strong> {server_name}<br>
                        <strong>Message:</strong> {message}<br>
                        <strong>Time:</strong> {alert.get('created_at', 'Unknown')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Resolve", key=f"dash_resolve_{alert_id}"):
                            resolve_resp = api.put(f"/alerts/{alert_id}/resolve")
                            if resolve_resp.status_code == 200:
                                st.success("Alert resolved successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to resolve alert")
                    
                    with col2:
                        if st.button("📊 View Server", key=f"dash_server_{alert_id}"):
                            st.session_state.selected_server = alert.get("server_id")
                            st.session_state.page = "Server Detail"
                            st.rerun()

def st_autorefresh(interval, key):
    """Simple auto-refresh for Streamlit."""
    import time
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    if time.time() - st.session_state.last_refresh > interval / 1000:
        st.session_state.last_refresh = time.time()
        st.rerun()
