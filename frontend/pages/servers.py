import streamlit as st
import time
from api.client import APIClient


def show_install_agent_wizard(api: APIClient, server_id: str, server_name: str):
    """Show the Install Agent wizard for a server."""
    st.markdown("### 📥 Install Monitoring Agent")
    
    # Step 1: OS Selection
    st.markdown("#### Step 1: Choose Operating System")
    os_choice = st.selectbox(
        "Select your server's operating system:",
        ["Windows", "Linux", "macOS"],
        key=f"os_{server_id}"
    )
    
    # Step 2: Generate enrollment token
    st.markdown("#### Step 2: Generate Enrollment Token")
    if st.button("Generate Enrollment Token", key=f"generate_{server_id}"):
        with st.spinner("Generating enrollment token..."):
            response = api.post(f"/agents/{server_id}/enrollment")
            if response.status_code == 200:
                enrollment_data = response.json()
                st.session_state[f"enrollment_{server_id}"] = enrollment_data
                st.success("Enrollment token generated successfully!")
                st.rerun()
            else:
                st.error(f"Failed to generate enrollment token: {response.text}")
    
    # Step 3: Show installation instructions
    if f"enrollment_{server_id}" in st.session_state:
        enrollment_data = st.session_state[f"enrollment_{server_id}"]
        enrollment_token = enrollment_data["enrollment_token"]
        api_url = enrollment_data["api_url"]
        
        st.markdown("#### Step 3: Installation Instructions")
        
        if os_choice == "Windows":
            st.info("""
            **Windows Installation:**
            
            1. Download the agent files to your target server
            2. Open PowerShell in the agent directory
            3. Run the following command:
            """)
            st.code(f'python agent.py --enroll "{enrollment_token}"', language="powershell")
            
        elif os_choice == "Linux":
            st.info("""
            **Linux Installation:**
            
            1. Download the agent files to your target server
            2. Install Python dependencies: `pip install -r requirements.txt`
            3. Run the following command:
            """)
            st.code(f'python3 agent.py --enroll "{enrollment_token}"', language="bash")
            
        else:  # macOS
            st.info("""
            **macOS Installation:**
            
            1. Download the agent files to your target server
            2. Install Python dependencies: `pip install -r requirements.txt`
            3. Run the following command:
            """)
            st.code(f'python3 agent.py --enroll "{enrollment_token}"', language="bash")
        
        # Step 4: Waiting for agent connection
        st.markdown("#### Step 4: Waiting for Agent Connection")
        st.info("Run the command above on your target server. The agent will automatically connect and start monitoring.")
        
        # Auto-refresh to check for agent connection
        if st.button("Check Agent Status", key=f"check_{server_id}"):
            response = api.get(f"/servers/{server_id}")
            if response.status_code == 200:
                server_data = response.json()
                if server_data.get("last_seen"):
                    st.success("✅ Agent Connected! The server is now being monitored.")
                    st.balloons()
                    del st.session_state[f"enrollment_{server_id}"]
                    st.rerun()
                else:
                    st.warning("⏳ Agent not yet connected. Please run the enrollment command on the target server.")
            else:
                st.error("Failed to check server status")


def render(api: APIClient):
    st.title("🖥️ Servers")

    # =========================================================
    # ADD SERVER
    # =========================================================

    with st.expander("➕ Add Server", expanded=False):

        with st.form("add_server_form"):

            name = st.text_input(
                "Server Name",
                placeholder="e.g. My Laptop"
            )

            ip_address = st.text_input(
                "IP Address",
                value="127.0.0.1"
            )

            server_type = st.selectbox(
                "Server Type",
                [
                    "local",
                    "web",
                    "db",
                    "api",
                    "cache",
                    "other",
                ],
            )

            tags = st.text_input(
                "Tags",
                placeholder="production, windows, laptop"
            )

            submitted = st.form_submit_button(
                "➕ Add Server",
                use_container_width=True
            )

            if submitted:

                if not name.strip():
                    st.error("❌ Server name is required.")
                    st.stop()

                if not ip_address.strip():
                    st.error("❌ IP address is required.")
                    st.stop()

                tags_list = [
                    tag.strip()
                    for tag in tags.split(",")
                    if tag.strip()
                ]

                try:

                    response = api.post(
                        "/servers",
                        json={
                            "name": name.strip(),
                            "ip_address": ip_address.strip(),
                            "server_type": server_type,
                            "tags": tags_list,
                        },
                    )

                    if response.status_code in (200, 201):

                        data = response.json()

                        st.success(
                            "✅ Server created successfully!"
                        )

                        # Show Server ID
                        if data.get("id"):
                            st.info(
                                f"🆔 Server ID: `{data['id']}`"
                            )

                        st.success(
                            "Now refresh the Servers page and install the agent."
                        )

                        st.rerun()

                    else:

                        st.error(
                            f"❌ Server creation failed "
                            f"(HTTP {response.status_code})"
                        )

                        st.code(
                            response.text,
                            language="text"
                        )

                except Exception as e:

                    st.error(
                        f"❌ Error creating server: {e}"
                    )

    # =========================================================
    # SEARCH AND FILTER
    # =========================================================
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        search_query = st.text_input("🔍 Search servers", placeholder="Search by name, IP, or tags...")
    
    with col2:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Online", "Offline", "Warning", "Critical"]
        )
    
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # =========================================================
    # AUTH CHECK
    # =========================================================

    token = st.session_state.get("token")

    if not token:

        st.error(
            "🔐 You are not logged in."
        )

        st.info(
            "Please logout and login again."
        )

        return

    # =========================================================
    # GET SERVERS
    # =========================================================

    try:

        response = api.get("/servers")

    except Exception as e:

        st.error(
            f"❌ Could not connect to backend:\n\n{e}"
        )

        return

    # =========================================================
    # RESPONSE STATUS
    # =========================================================

    if response.status_code == 401:

        st.error(
            "🔐 Authentication expired."
        )

        st.info(
            "Please logout and login again."
        )

        return

    if response.status_code == 403:

        st.error(
            "🚫 You don't have permission to view servers."
        )

        return

    if response.status_code != 200:

        st.error(
            f"❌ Failed to load servers.\n\n"
            f"HTTP Status: {response.status_code}"
        )

        st.code(
            response.text,
            language="text"
        )

        return

    # =========================================================
    # PARSE JSON
    # =========================================================

    try:

        data = response.json()

    except Exception:

        st.error(
            "❌ Backend returned invalid JSON."
        )

        st.code(
            response.text,
            language="text"
        )

        return

    # =========================================================
    # NORMALIZE SERVER RESPONSE
    # =========================================================

    if isinstance(data, dict):

        servers = data.get("items", [])

        if not servers:
            possible_servers = data.get("data")

            if isinstance(possible_servers, list):
                servers = possible_servers

            elif isinstance(possible_servers, dict):
                servers = possible_servers.get(
                    "items",
                    []
                )

    elif isinstance(data, list):

        servers = data

    else:

        servers = []

    # =========================================================
    # APPLY FILTERS
    # =========================================================
    
    if search_query:
        search_query = search_query.lower()
        servers = [
            s for s in servers
            if search_query in s.get("name", "").lower()
            or search_query in s.get("ip_address", "").lower()
            or search_query in str(s.get("tags", [])).lower()
        ]
    
    if status_filter != "All":
        if status_filter == "Online":
            servers = [s for s in servers if s.get("status") == "running"]
        elif status_filter == "Offline":
            servers = [s for s in servers if s.get("status") in ["stopped", "offline"]]
        elif status_filter == "Warning":
            servers = [s for s in servers if s.get("health_status") == "warning"]
        elif status_filter == "Critical":
            servers = [s for s in servers if s.get("health_status") == "critical"]

    # =========================================================
    # NO SERVERS
    # =========================================================

    if not servers:

        st.info(
            "📭 No servers found matching your criteria."
        )

        return

    # =========================================================
    # SERVER COUNT
    # =========================================================

    st.success(
        f"✅ {len(servers)} server(s) found."
    )

    # =========================================================
    # SERVER CARDS
    # =========================================================

    for server in servers:

        if not isinstance(server, dict):
            continue

        server_id = server.get("id")

        name = server.get(
            "name",
            "Unnamed Server"
        )

        # -----------------------------------------------------
        # GET LATEST SERVER DATA
        # -----------------------------------------------------

        if server_id:

            try:

                detail_response = api.get(
                    f"/servers/{server_id}"
                )

                if detail_response.status_code == 200:

                    latest_server = (
                        detail_response.json()
                    )

                    if isinstance(
                        latest_server,
                        dict
                    ):

                        server.update(
                            latest_server
                        )

            except Exception:
                pass

        # -----------------------------------------------------
        # SERVER VALUES
        # -----------------------------------------------------

        status = server.get(
            "status",
            "unknown"
        )

        health = server.get(
            "health_status",
            "unknown"
        )

        ip_address = server.get(
            "ip_address",
            "N/A"
        )

        server_type = server.get(
            "server_type",
            "N/A"
        )

        operating_system = server.get(
            "operating_system"
        ) or "N/A"

        hostname = server.get(
            "hostname"
        ) or "N/A"

        last_seen = server.get(
            "last_seen"
        ) or "Never"

        # -----------------------------------------------------
        # SAFE NUMBERS
        # -----------------------------------------------------

        try:
            cpu = float(
                server.get(
                    "cpu_usage",
                    0
                ) or 0
            )
        except (TypeError, ValueError):
            cpu = 0.0

        try:
            memory = float(
                server.get(
                    "memory_usage",
                    0
                ) or 0
            )
        except (TypeError, ValueError):
            memory = 0.0

        try:
            disk = float(
                server.get(
                    "disk_usage",
                    0
                ) or 0
            )
        except (TypeError, ValueError):
            disk = 0.0

        # -----------------------------------------------------
        # HEALTH ICON
        # -----------------------------------------------------

        health_icons = {
            "healthy": "🟢",
            "warning": "🟡",
            "critical": "🔴",
            "offline": "⚫",
            "unknown": "⚪",
        }

        icon = health_icons.get(
            str(health).lower(),
            "⚪"
        )

        # =====================================================
        # SERVER CONTAINER
        # =====================================================

        with st.container():

            col1, col2, col3, col4 = st.columns(
                [3, 2, 2, 2]
            )

            # -------------------------------------------------
            # SERVER INFORMATION
            # -------------------------------------------------

            with col1:

                st.subheader(
                    f"{icon} {name}"
                )

                st.write(
                    f"**IP:** {ip_address}  "
                    f"| **Type:** {server_type}"
                )

                st.write(
                    f"**Status:** {status}  "
                    f"| **Health:** {health}"
                )

                st.write(
                    f"**Hostname:** {hostname}"
                )

                st.write(
                    f"**OS:** {operating_system}"
                )

                st.write(
                    f"**Last seen:** {last_seen}"
                )

            # -------------------------------------------------
            # METRICS
            # -------------------------------------------------

            with col2:

                st.metric(
                    "CPU",
                    f"{cpu:.1f}%"
                )

                st.metric(
                    "Memory",
                    f"{memory:.1f}%"
                )

                st.metric(
                    "Disk",
                    f"{disk:.1f}%"
                )

            # -------------------------------------------------
            # ACTIONS
            # -------------------------------------------------

            with col3:

                if server_id:

                    if st.button(
                        "📊 Details",
                        key=f"details_{server_id}",
                        use_container_width=True
                    ):

                        st.session_state.selected_server = (
                            server_id
                        )

                        st.session_state.page = (
                            "Server Detail"
                        )

                        st.rerun()

                    if st.button(
                        "📥 Install Agent",
                        key=f"install_{server_id}",
                        use_container_width=True
                    ):
                        st.session_state[f"show_install_{server_id}"] = True
                        st.rerun()

            # -------------------------------------------------
            # DELETE
            # -------------------------------------------------

            with col4:

                if server_id:

                    if st.button(
                        "🗑️ Delete",
                        key=f"delete_{server_id}",
                        use_container_width=True
                    ):

                        try:

                            delete_response = api.delete(
                                f"/servers/{server_id}"
                            )

                            if delete_response.status_code in (
                                200,
                                204
                            ):

                                st.success(
                                    "✅ Server deleted."
                                )

                                st.rerun()

                            else:

                                st.error(
                                    f"❌ Delete failed "
                                    f"(HTTP "
                                    f"{delete_response.status_code})"
                                )

                                st.code(
                                    delete_response.text,
                                    language="text"
                                )

                        except Exception as e:

                            st.error(
                                f"❌ Delete error: {e}"
                            )

            # -------------------------------------------------
            # INSTALL AGENT WIZARD
            # -------------------------------------------------

            if st.session_state.get(f"show_install_{server_id}"):
                with st.expander("📥 Install Agent Wizard", expanded=True):
                    show_install_agent_wizard(api, server_id, name)
                    if st.button("Close Wizard", key=f"close_install_{server_id}"):
                        del st.session_state[f"show_install_{server_id}"]
                        st.rerun()

            st.divider()