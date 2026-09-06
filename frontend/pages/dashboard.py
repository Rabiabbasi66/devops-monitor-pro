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
            f"{stats.get('avg_memory_usage', 0):.1f}%",
            delta=None,
            help="Average memory usage across all servers"
        )
    
    with c9:
        st.metric(
            "🖥️ Avg CPU", 
            f"{stats.get('avg_cpu_usage', 0):.1f}%",
            delta=None,
            help="Average CPU usage across all servers"
        )

    st.divider()

    # =========================================================
    # SERVER OVERVIEW CARDS
    # =========================================================
    
    st.markdown("### 🖥️ Server Overview")
    
    servers_resp = api.get("/servers")
    servers = servers_resp.json() if servers_resp.status_code == 200 else []
    
    if not servers:
        st.warning("No servers data available")
        return
    
    # Create beautiful server cards
    for i in range(0, len(servers), 3):
        cols = st.columns(3)
        for j, server in enumerate(servers[i:i+3]):
            with cols[j]:
                # Get detailed server data
                server_id = server.get("id")
                if server_id:
                    detail_resp = api.get(f"/servers/{server_id}")
                    if detail_resp.status_code == 200:
                        server.update(detail_resp.json())
                
                # Extract values safely
                name = server.get("name", "Unknown")
                status = server.get("status", "unknown")
                health = server.get("health_status", "unknown")
                
                try:
                    cpu = float(server.get("cpu_usage", 0) or 0)
                except (TypeError, ValueError):
                    cpu = 0.0
                
                try:
                    memory = float(server.get("memory_usage", 0) or 0)
                except (TypeError, ValueError):
                    memory = 0.0
                
                try:
                    disk = float(server.get("disk_usage", 0) or 0)
                except (TypeError, ValueError):
                    disk = 0.0
                
                # Health indicators
                health_colors = {
                    "healthy": "#00ff00",
                    "warning": "#ffaa00",
                    "critical": "#ff0000",
                    "offline": "#666666",
                    "unknown": "#aaaaaa"
                }
                color = health_colors.get(str(health).lower(), "#aaaaaa")
                
                # Card styling
                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
                    border-left: 4px solid {color};
                    padding: 15px;
                    border-radius: 8px;
                    margin-bottom: 10px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                ">
                    <h4 style="margin: 0 0 10px 0; color: white;">{name}</h4>
                    <div style="display: flex; gap: 15px; color: #ccc; font-size: 12px;">
                        <span>Status: <strong>{status}</strong></span>
                        <span>Health: <strong>{health}</strong></span>
                    </div>
                    <div style="margin-top: 10px; display: flex; gap: 15px;">
                        <div style="flex: 1;">
                            <div style="font-size: 11px; color: #888;">CPU</div>
                            <div style="font-size: 16px; font-weight: bold; color: white;">{cpu:.1f}%</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 11px; color: #888;">Memory</div>
                            <div style="font-size: 16px; font-weight: bold; color: white;">{memory:.1f}%</div>
                        </div>
                        <div style="flex: 1;">
                            <div style="font-size: 11px; color: #888;">Disk</div>
                            <div style="font-size: 16px; font-weight: bold; color: white;">{disk:.1f}%</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("📊 View Details", key=f"dash_detail_{server_id}", use_container_width=True):
                    st.session_state.selected_server = server_id
                    st.session_state.page = "Server Detail"
                    st.rerun()

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
        
        # Network (placeholder - would need network data)
        fig.add_trace(
            go.Scatter(
                x=names,
                y=[0] * len(servers),  # Placeholder
                name="Network",
                mode='markers+lines',
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
