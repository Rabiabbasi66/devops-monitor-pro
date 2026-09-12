# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the DevOps Monitor Pro Windows agent.

Produces a single windowed executable (agent/dist/DevOpsMonitorAgent.exe) that
bundles the Python runtime, agent code, GUI and all dependencies - a client
does NOT need Python installed.

Build with (from the agent/ directory):

    .\\build_windows.ps1

Security notes:
  - No credentials, tokens, MongoDB URIs or .env files are bundled. The
    production API URL lives in agent/config.py (public default) and can be
    overridden at runtime via the API_URL environment variable.
  - Enrollment happens at runtime via POST /api/agents/enroll; the permanent
    agent token is only stored locally after successful enrollment.
"""

a = Analysis(
    ["agent.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # requests + certifi (TLS trust store) - required for HTTPS to production
        "requests",
        "certifi",
        # psutil - metric collectors
        "psutil",
        "psutil._pswindows",
        # pydantic-settings pulls pydantic v2; include pieces hooks may miss
        "pydantic",
        "pydantic_settings",
        "annotated_types",
        "python_dotenv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the bundle lean; nothing here is used by the agent.
        "pytest",
        "setuptools",
        "distutils",
        "unittest",
        "xmlrpc",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="DevOpsMonitorAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # GUI app: no console window flashes when the client double-clicks the exe.
    console=False,
    icon=None,
)
