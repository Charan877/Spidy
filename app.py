"""SPIDY — Autonomous Software Engineering.

Primary application entrypoint.
Launches the high-performance Starlette/Uvicorn server hosting the
immersive React 18 + Three.js / React Three Fiber 3D computational world.
"""

import sys


def _is_streamlit_environment() -> bool:
    """Check if app.py is being executed by Streamlit's script runner."""
    if "streamlit" in sys.modules:
        try:
            from streamlit.runtime import exists
            if exists():
                return True
        except Exception:
            pass
    for arg in sys.argv:
        if "streamlit" in arg.lower():
            return True
    return False


if _is_streamlit_environment():
    import streamlit as st
    from server import start_background_server

    # Start native engine on next free port (e.g. 8502) without colliding with Streamlit's port 8501
    server_port = start_background_server(preferred_port=8502)

    st.set_page_config(
        page_title="SPIDY — Autonomous Software Engineering",
        page_icon="✦",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    target_url = f"http://localhost:{server_port}"

    st.markdown(
        f"""
        <style>
          header, footer, [data-testid="stHeader"], [data-testid="stToolbar"] {{ display: none !important; }}
          body, [data-testid="stApp"], .main, .block-container {{
            background: #040711 !important;
            padding: 0 !important;
            margin: 0 !important;
            max-width: 100vw !important;
            height: 100vh !important;
            overflow: hidden !important;
          }}
          .spidy-frame {{
            border: none !important;
            width: 100vw !important;
            height: 100vh !important;
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            z-index: 9999 !important;
            background: #040711 !important;
          }}
        </style>
        <iframe class="spidy-frame" src="{target_url}"></iframe>
        <script>
          if (window.top && window.top.location.href.indexOf(":{server_port}") === -1) {{
            window.top.location.href = "{target_url}";
          }}
        </script>
        """,
        unsafe_allow_html=True,
    )
else:
    from server import main

    main()