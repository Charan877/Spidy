"""Curated Creative-Technology Stylesheet for NOVA Code Lab.

Transforms the presentation layer into an immersive, typography-driven, cinematic
computational environment inspired by modern experimental tech design.
"""

GLOBAL_CSS = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Space+Grotesk:wght@300;400;500;600;700&family=Syne:wght@700;800&display=swap');

  /* Root variables */
  :root {
    --bg-base: #06070a;
    --bg-surface: #0c0e14;
    --bg-glass: rgba(12, 14, 20, 0.7);
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-active: rgba(99, 102, 241, 0.35);
    --accent-indigo: #6366f1;
    --accent-violet: #818cf8;
    --accent-emerald: #10b981;
    --accent-amber: #f59e0b;
    --accent-rose: #f43f5e;
    --text-pure: #f8fafc;
    --text-muted: #94a3b8;
    --text-faint: #475569;
    --font-display: 'Syne', sans-serif;
    --font-mono: 'Space Grotesk', monospace, sans-serif;
    --font-body: 'Inter', system-ui, sans-serif;
  }

  /* Reset & Global Shell */
  html, body, [data-testid="stApp"] {
    background-color: var(--bg-base) !important;
    color: var(--text-pure);
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
  }

  /* Remove default Streamlit chrome */
  header[data-testid="stHeader"],
  #MainMenu,
  footer,
  div[data-testid="stToolbar"],
  div[data-testid="stDecoration"] {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
  }

  /* Responsive Main Container */
  .main .block-container {
    max-width: 1540px !important;
    padding: 1.8rem 3rem 4rem 3rem !important;
  }

  @media (max-width: 1024px) {
    .main .block-container {
      padding: 1.2rem 1.5rem 3rem 1.5rem !important;
    }
  }

  /* Atmospheric Background Layer */
  [data-testid="stAppViewContainer"] {
    background:
      radial-gradient(1000px 500px at 15% 10%, rgba(99, 102, 241, 0.07), transparent 60%),
      radial-gradient(800px 500px at 85% 85%, rgba(168, 85, 247, 0.05), transparent 60%),
      radial-gradient(600px 400px at 50% 50%, rgba(16, 185, 129, 0.02), transparent 70%),
      #06070a !important;
  }

  /* Subtle Computational Dot/Grid Mesh */
  [data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
    background-size: 36px 36px;
    opacity: 0.45;
    mask-image: radial-gradient(ellipse at 50% 30%, rgba(0,0,0,0.8), transparent 85%);
  }

  /* Minimal Navigation */
  .nova-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0 1.6rem 0;
    border-bottom: 1px solid var(--border-subtle);
    margin-bottom: 2.2rem;
  }

  .nova-brand {
    font-family: var(--font-display);
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .nova-brand-badge {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    padding: 0.15rem 0.45rem;
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .nova-nav-links {
    display: flex;
    align-items: center;
    gap: 1.8rem;
  }

  .nova-nav-link {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--text-muted);
    text-decoration: none;
    transition: color 0.3s ease;
    cursor: pointer;
  }

  .nova-nav-link:hover, .nova-nav-link.active {
    color: #ffffff;
  }

  .nova-status-pill {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    letter-spacing: 0.12em;
    color: var(--text-muted);
  }

  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent-emerald);
    box-shadow: 0 0 10px var(--accent-emerald);
    animation: pulse 3s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.85); }
  }

  /* Huge Display Typography */
  .nova-hero-huge {
    font-family: var(--font-display);
    font-size: clamp(3.2rem, 6.2vw, 6.5rem);
    font-weight: 800;
    line-height: 0.94;
    letter-spacing: -0.04em;
    text-transform: uppercase;
    color: #ffffff;
    margin-bottom: 1.8rem;
  }

  .nova-hero-sub {
    font-family: var(--font-mono);
    font-size: clamp(0.78rem, 1.1vw, 0.95rem);
    letter-spacing: 0.26em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 0.8rem;
  }

  .nova-text-gradient {
    background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  /* Minimal Command / Input Area */
  .nova-command-box {
    background: rgba(14, 17, 24, 0.65);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.4rem;
    transition: border-color 0.4s ease, box-shadow 0.4s ease;
    backdrop-filter: blur(16px);
  }

  .nova-command-box:focus-within {
    border-color: var(--border-active);
    box-shadow: 0 0 40px rgba(99, 102, 241, 0.12);
  }

  /* Streamlit text input override */
  .stTextArea textarea {
    background: transparent !important;
    border: none !important;
    color: #f8fafc !important;
    font-family: var(--font-body) !important;
    font-size: 1.15rem !important;
    line-height: 1.5 !important;
    padding: 0.2rem 0 !important;
    box-shadow: none !important;
    resize: none !important;
  }

  .stTextArea textarea:focus {
    outline: none !important;
    border: none !important;
  }

  .stTextArea textarea::placeholder {
    color: #475569 !important;
  }

  /* Streamlit Selectbox minimal styling */
  .stSelectbox div[data-baseweb="select"] {
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: var(--text-pure) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.82rem !important;
  }

  /* Minimal Button Styling */
  .stButton button {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    color: #f8fafc !important;
    font-family: var(--font-mono) !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    padding: 0.65rem 1.4rem !important;
    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1) !important;
    box-shadow: none !important;
  }

  .stButton button:hover {
    background: rgba(99, 102, 241, 0.16) !important;
    border-color: var(--accent-indigo) !important;
    color: #ffffff !important;
    box-shadow: 0 0 24px rgba(99, 102, 241, 0.25) !important;
    transform: translateY(-1px);
  }

  .stButton button[kind="primary"] {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.9), rgba(79, 70, 229, 0.95)) !important;
    border: 1px solid rgba(165, 180, 252, 0.4) !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    box-shadow: 0 0 30px rgba(99, 102, 241, 0.3) !important;
  }

  .stButton button[kind="primary"]:hover {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    border-color: #ffffff !important;
    box-shadow: 0 0 45px rgba(99, 102, 241, 0.45) !important;
  }

  /* Preset tag buttons */
  .nova-preset-tag {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    padding: 0.25rem 0.75rem;
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    margin-right: 0.5rem;
    margin-bottom: 0.5rem;
    transition: all 0.25s ease;
    cursor: pointer;
  }

  .nova-preset-tag:hover {
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.25);
    background: rgba(255, 255, 255, 0.03);
  }

  /* Editorial Stat Blocks (Right Column) */
  .nova-stat-block {
    margin-bottom: 1.8rem;
  }

  .nova-stat-val {
    font-family: var(--font-display);
    font-size: clamp(1.8rem, 3.2vw, 2.8rem);
    font-weight: 800;
    line-height: 1.0;
    letter-spacing: -0.03em;
    color: #f8fafc;
  }

  .nova-stat-lbl {
    font-family: var(--font-mono);
    font-size: 0.68rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--text-faint);
    margin-top: 0.35rem;
  }

  /* Compact Stage Indicators */
  .nova-stage-strip {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    margin: 1.2rem 0;
    flex-wrap: wrap;
  }

  .nova-stage-pill {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 0.2rem 0.6rem;
    border-radius: 4px;
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .nova-stage-pill.completed {
    color: var(--accent-emerald);
    border: 1px solid rgba(16, 185, 129, 0.25);
    background: rgba(16, 185, 129, 0.06);
  }

  .nova-stage-pill.active {
    color: #ffffff;
    border: 1px solid var(--accent-indigo);
    background: rgba(99, 102, 241, 0.18);
    box-shadow: 0 0 16px rgba(99, 102, 241, 0.3);
  }

  .nova-stage-pill.waiting {
    color: var(--text-faint);
    border: 1px solid rgba(255, 255, 255, 0.04);
  }

  /* Cinematic Activity Stream (Latest 3-4 items) */
  .nova-stream {
    margin-top: 1.4rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .nova-stream-item {
    display: flex;
    align-items: baseline;
    gap: 0.8rem;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--text-muted);
    border-left: 1px solid var(--border-subtle);
    padding-left: 0.8rem;
    transition: border-color 0.3s ease;
  }

  .nova-stream-item.active {
    border-color: var(--accent-indigo);
    color: #f1f5f9;
  }

  .nova-stream-agent {
    font-size: 0.68rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent-violet);
    flex-shrink: 0;
    min-width: 90px;
  }

  .nova-stream-msg {
    color: #cbd5e1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Progressive Disclosure Drawer / Panel */
  .nova-drawer-container {
    background: rgba(10, 12, 18, 0.94);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1.8rem;
    margin-top: 1.5rem;
    margin-bottom: 2rem;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(20px);
    animation: fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1);
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .nova-drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 1rem;
    margin-bottom: 1.4rem;
  }

  .nova-drawer-title {
    font-family: var(--font-display);
    font-size: 1.3rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    text-transform: uppercase;
  }

  /* Editorial Project History List */
  .nova-history-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    transition: background 0.2s ease;
  }

  .nova-history-row:hover {
    background: rgba(255, 255, 255, 0.015);
  }

  .nova-history-name {
    font-family: var(--font-display);
    font-size: 1.1rem;
    font-weight: 700;
    color: #f8fafc;
  }

  .nova-history-meta {
    font-family: var(--font-mono);
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
  }

  .nova-history-right {
    text-align: right;
    font-family: var(--font-mono);
    font-size: 0.8rem;
  }

  /* Terminal Log Display */
  .nova-terminal {
    background: #050608;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 1.2rem;
    font-family: Consolas, monospace;
    font-size: 0.78rem;
    color: #a5b4fc;
    line-height: 1.6;
    max-height: 440px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* Live Preview Container */
  .nova-preview-frame {
    width: 100%;
    height: 560px;
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    background: #000000;
    overflow: hidden;
    margin-top: 1.4rem;
  }
</style>
"""
