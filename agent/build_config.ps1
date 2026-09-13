# =============================================================================
# DevOps Monitor Pro - AGENT BUILD CONFIGURATION
# =============================================================================
#
#   THIS IS THE ONE PLACE TO CONFIGURE THE PRODUCTION AGENT BUILD.
#   Change the values below, then run agent\build_windows.ps1.
#
# Override any value without editing this file:
#   .\build_windows.ps1 -ApiUrl "https://your-backend.example.com/api"
#
# =============================================================================

# -----------------------------------------------------------------------------
# PRODUCTION API URL  <-- SET THIS
# -----------------------------------------------------------------------------
# Base REST URL of your FastAPI backend. The agent enrollment endpoint is
# {API_URL}/agents/enroll and metrics go to {API_URL}/monitoring/metrics.
#
# Examples:
#   https://devops-monitor-pro.vercel.app/api        (Vercel)
#   https://api.your-domain.com/api                  (custom domain)
#
# SECURITY:
#   - MUST be HTTPS in production. The build FAILS if you set an http:// URL
#     here, so localhost can never ship inside a client installer.
#   - Never put localhost in production builds; use -ApiUrl to override
#     locally when you need to test against a dev backend.
# -----------------------------------------------------------------------------
$ApiUrl = "https://devops-monitor-pro.vercel.app/api"

# -----------------------------------------------------------------------------
# Installer metadata (shows in Windows "Apps & Features" and the setup wizard)
# -----------------------------------------------------------------------------
$AppVersion      = "2.1.0"
$AppPublisher    = "DevOps Monitor Pro"
$AppPublisherUrl = "https://github.com/Rabiabbasi66/devops-monitor-pro"

# GitHub repository used by CI (GitHub Actions) to locate the checkout.
$GitHubRepo = "Rabiabbasi66/devops-monitor-pro"
