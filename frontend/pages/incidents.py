"""Incidents management page."""
import streamlit as st
from datetime import datetime

from api.client import APIClient


def _fmt_dt(dt_str: str) -> str:
    if not dt_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt_str)[:19]


def render(api: APIClient):
    st.title("🚨 Incidents")

    # ─── Controls ───────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All", "open", "investigating", "identified", "monitoring", "resolved"],
            key="inc_status_filter",
        )
    with col2:
        severity_filter = st.selectbox(
            "Severity",
            ["All", "critical", "high", "warning", "info"],
            key="inc_sev_filter",
        )
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with col4:
        if st.button("➕ New Incident", use_container_width=True):
            st.session_state["show_create_incident"] = True

    # ─── Create incident form ────────────────────────────────────────────────
    if st.session_state.get("show_create_incident"):
        with st.expander("➕ Create New Incident", expanded=True):
            with st.form("create_incident_form"):
                title = st.text_input("Title *", placeholder="Brief description of the incident")
                description = st.text_area("Description", placeholder="Detailed description...")
                severity = st.selectbox("Severity", ["high", "critical", "warning", "info"])
                submitted = st.form_submit_button("Create Incident", use_container_width=True)

                if submitted:
                    if not title.strip():
                        st.error("Title is required")
                    else:
                        resp = api.post(
                            "/incidents/",
                            json={
                                "title": title.strip(),
                                "description": description.strip() or None,
                                "severity": severity,
                            },
                        )
                        if resp.status_code == 200:
                            st.success("✅ Incident created")
                            st.session_state.pop("show_create_incident", None)
                            st.rerun()
                        else:
                            st.error(f"Failed to create incident: {resp.text}")

            if st.button("Cancel", key="cancel_create_inc"):
                st.session_state.pop("show_create_incident", None)
                st.rerun()

    st.divider()

    # ─── Load incidents ──────────────────────────────────────────────────────
    params = {}
    if status_filter != "All":
        params["status"] = status_filter
    if severity_filter != "All":
        params["severity"] = severity_filter

    resp = api.get("/incidents/", **params)
    if resp.status_code != 200:
        st.error(f"Failed to load incidents (HTTP {resp.status_code})")
        return

    incidents = resp.json()
    if not isinstance(incidents, list):
        incidents = []

    if not incidents:
        st.info("📭 No incidents found.")
        return

    st.markdown(f"**{len(incidents)} incident(s)**")

    # ─── Incident cards ──────────────────────────────────────────────────────
    severity_icons = {"critical": "🔴", "high": "🟠", "warning": "🟡", "info": "🔵"}
    status_icons = {
        "open": "🔓", "investigating": "🔍", "identified": "🎯",
        "monitoring": "👁️", "resolved": "✅",
    }

    for inc in incidents:
        inc_id = inc.get("id")
        sev = inc.get("severity", "high")
        status = inc.get("status", "open")
        title = inc.get("title", "Untitled")
        sev_icon = severity_icons.get(sev, "⚪")
        st_icon = status_icons.get(status, "❓")

        with st.expander(f"{sev_icon} [{status.upper()}] {st_icon} {title}", expanded=(status == "open")):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Severity:** {sev.upper()}")
            c2.write(f"**Status:** {status.upper()}")
            c3.write(f"**Created:** {_fmt_dt(inc.get('created_at'))}")

            if inc.get("description"):
                st.write(f"**Description:** {inc['description']}")

            if inc.get("resolved_at"):
                c4, c5 = st.columns(2)
                c4.write(f"**Resolved:** {_fmt_dt(inc.get('resolved_at'))}")
                if inc.get("duration_seconds"):
                    mins = int(inc["duration_seconds"] // 60)
                    c5.write(f"**Duration:** {mins} min")

            if inc.get("affected_servers"):
                st.write(f"**Affected servers:** {', '.join(inc['affected_servers'])}")

            st.markdown("**Actions:**")
            act_cols = st.columns(4)

            with act_cols[0]:
                if status in ("open",) and st.button("🔍 Acknowledge", key=f"ack_inc_{inc_id}"):
                    r = api.post(f"/incidents/{inc_id}/acknowledge")
                    if r.status_code == 200:
                        st.success("Acknowledged")
                        st.rerun()

            with act_cols[1]:
                if status != "resolved" and st.button("✅ Resolve", key=f"res_inc_{inc_id}"):
                    r = api.post(f"/incidents/{inc_id}/resolve")
                    if r.status_code == 200:
                        st.success("Resolved")
                        st.rerun()

            with act_cols[2]:
                if status == "resolved" and st.button("🔄 Reopen", key=f"reopen_inc_{inc_id}"):
                    r = api.post(f"/incidents/{inc_id}/reopen")
                    if r.status_code == 200:
                        st.success("Reopened")
                        st.rerun()

            with act_cols[3]:
                if st.button("🗑️ Delete", key=f"del_inc_{inc_id}"):
                    r = api.delete(f"/incidents/{inc_id}")
                    if r.status_code == 200:
                        st.success("Deleted")
                        st.rerun()
