import streamlit as st
import streamlit.components.v1 as components


def get_screen_width():
    # Try request headers first (works better on Streamlit Cloud/mobile browsers).
    try:
        raw_headers = getattr(st.context, "headers", {})
        headers = {str(k).lower(): str(v) for k, v in dict(raw_headers).items()}

        viewport_width = headers.get("sec-ch-viewport-width", "") or headers.get("viewport-width", "")
        if str(viewport_width).isdigit():
            return int(viewport_width)

        user_agent = headers.get("user-agent", "").lower()
        if any(token in user_agent for token in ["android", "iphone", "ipad", "ipod", "mobile"]):
            return 390
    except Exception:
        pass

    # Fallback for local/dev where request headers may be unavailable.
    components.html(
        """
        <script>
        const width = window.innerWidth;
        </script>
        """,
        height=0,
    )
    return 1024


def is_mobile(width):
    return width < 768


def apply_styles():
    st.markdown(
        """
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="theme-color" content="#1976d2">
        <meta name="application-name" content="ROSCA">
        <meta name="apple-mobile-web-app-capable" content="yes">
        <meta name="apple-mobile-web-app-title" content="ROSCA">
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(135deg, #e3f2fd, #fce4ec, #e8f5e9);
            background-attachment: fixed;
        }

        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        .metric-card {
            padding: 16px;
            border-radius: 16px;
            margin-bottom: 14px;
            color: white;
            font-weight: 500;
            box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            transition: all 0.3s ease-in-out;
            cursor: pointer;
        }

        .metric-card:hover {
            transform: translateY(-6px) scale(1.02);
            box-shadow: 0px 8px 20px rgba(0,0,0,0.25);
        }

        .blue { background: linear-gradient(135deg, #42a5f5, #1e88e5); }
        .green { background: linear-gradient(135deg, #66bb6a, #2e7d32); }
        .orange { background: linear-gradient(135deg, #ffa726, #ef6c00); }
        .purple { background: linear-gradient(135deg, #ab47bc, #6a1b9a); }
        .red { background: linear-gradient(135deg, #ef5350, #c62828); }
        .teal { background: linear-gradient(135deg, #26c6da, #00838f); }
        .pink { background: linear-gradient(135deg, #ec407a, #ad1457); }
        .indigo { background: linear-gradient(135deg, #5c6bc0, #283593); }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        [data-testid="stHeader"] { display: none; }
        [data-testid="stToolbar"] { display: none !important; }
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="stDecoration"] { display: none !important; }
        [data-testid="stStatusWidget"] { display: none !important; }

        .welcome-banner {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: transparent;
            color: #1a1a1a;
            border-radius: 0;
            padding: 0;
            margin-bottom: 8px;
            font-weight: 600;
            box-shadow: none;
            border: none;
        }

        .welcome-text {
            font-size: 18px;
            font-weight: 400;
            color: #1e88e5;
        }

        .welcome-logout {
            background: linear-gradient(135deg, #ef5350, #c62828);
            color: #ffffff !important;
            padding: 6px 14px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 700;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.2);
            white-space: nowrap;
        }

        .welcome-logout:hover {
            filter: brightness(0.95);
            text-decoration: none;
        }

        button[title="View fullscreen"] {
            display: none !important;
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
            min-height: 3rem;
            border-radius: 14px;
            border: 1px solid #d4e3f7;
            background: linear-gradient(180deg, #ffffff, #eef5ff);
            color: #123a68;
            font-weight: 600;
            box-shadow: 0px 4px 10px rgba(17, 57, 102, 0.08);
            margin-bottom: 0.35rem;
        }

        [data-testid="stSidebar"] .stButton > button:hover {
            border-color: #1e88e5;
            color: #0b5cad;
            box-shadow: 0px 8px 18px rgba(30, 136, 229, 0.18);
        }

        html, body, .stApp {
            overflow-x: hidden !important;
        }

        @media (max-width: 768px) {
            header {visibility: hidden;}
            [data-testid="stHeader"] { display: none; }
            [data-testid="stToolbar"] { display: none !important; }
            [data-testid="collapsedControl"] { display: none !important; }

            .block-container {
                padding: 0.5rem !important;
            }

            h1, h2, h3 {
                font-size: 1.2rem !important;
            }

            .metric-card:hover {
                transform: none;
                box-shadow: 0px 4px 12px rgba(0,0,0,0.15);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def metric_card(title, value, color, icon="📊"):
    st.markdown(
        f"""
        <div class="metric-card {color}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="font-size:14px;">{title}</div>
                <div style="font-size:22px;">{icon}</div>
            </div>
            <div style="font-size:22px; font-weight:bold; margin-top:5px;">
                {value}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
