import streamlit as st

from api.client import APIClient
from pages import alerts, dashboard, notifications, server_detail, servers, settings


def login_page(api: APIClient):
    """Modern login page with improved UX."""
    
    # Custom CSS for modern styling
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .stButton>button {
        width: 100%;
        margin-top: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("# 🔐 DevOps Monitor Pro")
    st.markdown("### Production-Ready Infrastructure Monitoring")
    
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])

    with tab1:
        with st.form("login", clear_on_submit=False):
            st.markdown("#### Login to your account")
            
            email = st.text_input(
                "📧 Email Address",
                placeholder="your@email.com",
                help="Enter your registered email address"
            )
            
            password = st.text_input(
                "🔒 Password",
                type="password",
                placeholder="••••••••",
                help="Enter your password"
            )
            
            submitted = st.form_submit_button("🚀 Login", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.error("❌ Please fill in all fields")
                    return
                
                with st.spinner("Authenticating..."):
                    if api.login(email, password):
                        st.success("✅ Login successful!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("❌ Invalid email or password")
                        st.info("Please check your credentials and try again")

    with tab2:
        with st.form("register", clear_on_submit=False):
            st.markdown("#### Create a new account")
            
            email = st.text_input(
                "📧 Email Address",
                key="reg_email",
                placeholder="your@email.com",
                help="Enter your email address"
            )
            
            username = st.text_input(
                "👤 Username",
                placeholder="johndoe",
                help="Choose a unique username"
            )
            
            full_name = st.text_input(
                "📛 Full Name",
                placeholder="John Doe",
                help="Your full name (optional)"
            )
            
            password = st.text_input(
                "🔒 Password",
                type="password",
                key="reg_pass",
                placeholder="••••••••",
                help="Choose a strong password"
            )
            
            confirm = st.text_input(
                "🔒 Confirm Password",
                type="password",
                placeholder="••••••••",
                help="Re-enter your password"
            )
            
            submitted = st.form_submit_button("📝 Register", use_container_width=True)
            
            if submitted:
                if not email or not username or not password:
                    st.error("❌ Please fill in all required fields")
                    return
                
                if password != confirm:
                    st.error("❌ Passwords do not match")
                    return
                
                if len(password) < 8:
                    st.error("❌ Password must be at least 8 characters")
                    return
                
                with st.spinner("Creating account..."):
                    if api.register(email, username, password, confirm, full_name):
                        st.success("✅ Registration successful!")
                        st.info("👉 Please login with your new account")
                    else:
                        st.error("❌ Registration failed")
                        st.info("The email or username may already be in use")


def main():
    # Modern page configuration
    st.set_page_config(
        page_title="DevOps Monitor Pro",
        page_icon="🔧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for modern dark theme
    st.markdown("""
    <style>
    .stApp {
        background-color: #0d1117;
    }
    .main {
        background-color: #161b22;
    }
    .stSidebar {
        background-color: #0d1117;
    }
    h1, h2, h3 {
        color: #ffffff;
    }
    .metric-container {
        background-color: #1e1e1e;
        border-radius: 8px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }
    </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    for key, default in {
        "token": None,
        "user": None,
        "page": "Dashboard",
        "selected_server": None,
    }.items():
        if key not in st.session_state:
            st.session_state[key] = default

    api = APIClient()

    # Modern sidebar
    with st.sidebar:
        st.markdown("# 🔧 DevOps Monitor")
        st.markdown("---")
        
        if st.session_state.token:
            user = st.session_state.user or {}
            username = user.get('username', 'User')
            email = user.get('email', '')
            
            st.markdown(f"### 👤 {username}")
            st.caption(f"{email}")
            
            st.markdown("---")
            
            # Navigation with icons
            pages = {
                "Dashboard": "📊",
                "Servers": "🖥️",
                "Server Detail": "📈",
                "Alerts": "🔔",
                "Notifications": "📬",
                "Settings": "⚙️"
            }
            
            selected_page = st.radio(
                "Navigation",
                list(pages.keys()),
                format_func=lambda x: f"{pages[x]} {x}",
                label_visibility="collapsed"
            )
            
            st.session_state.page = selected_page
            
            st.markdown("---")
            
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.token = None
                st.session_state.user = None
                st.success("Logged out successfully")
                st.rerun()
        else:
            st.info("👉 Please login to access the dashboard")

    # Show login page if not authenticated
    if not st.session_state.token:
        login_page(api)
        return

    # Route to appropriate page
    page = st.session_state.page
    if page == "Dashboard":
        dashboard.render(api)
    elif page == "Servers":
        servers.render(api)
    elif page == "Server Detail":
        server_detail.render(api)
    elif page == "Alerts":
        alerts.render(api)
    elif page == "Notifications":
        notifications.render(api)
    elif page == "Settings":
        settings.render(api)


if __name__ == "__main__":
    main()
