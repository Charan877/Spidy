from backend.core.brand import APP_NAME, APP_TAGLINE


def render_hero(api_online: bool, model_name: str) -> str:
    status_text = "ONLINE" if api_online else "KEY MISSING"
    status_color = "#34d399" if api_online else "#f87171"

    return f"""
<div style="position:relative;width:100%;height:180px;overflow:hidden;border-radius:14px;
 border:1px solid rgba(56,189,248,.25);background:radial-gradient(800px 300px at 20% 10%,rgba(56,130,246,.18),transparent 60%),
 radial-gradient(600px 300px at 90% 90%,rgba(168,85,247,.14),transparent 60%),#070b14;
 box-shadow:0 0 35px rgba(56,189,248,.10);">
  <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:1rem;">
    <div style="font-family:Consolas,monospace;font-size:.75rem;letter-spacing:.4em;color:#38bdf8;text-shadow:0 0 12px rgba(56,189,248,.8);">
      {APP_NAME} // {APP_TAGLINE.upper()}
    </div>
    <div style="font-size:2.1rem;font-weight:800;letter-spacing:.12em;color:#f8fafc;margin:.25rem 0;
      text-shadow:0 0 24px rgba(56,189,248,.6);">
      {APP_NAME}
    </div>
    <div style="font-family:Consolas,monospace;font-size:.78rem;letter-spacing:.25em;color:#94a3b8;">
      BUILD • RUN • TEST • DEBUG • LIVE PREVIEW
    </div>
    <div style="margin-top:.8rem;display:flex;gap:.6rem;flex-wrap:wrap;justify-content:center;">
      <span style="font-family:Consolas,monospace;font-size:.7rem;letter-spacing:.12em;color:{status_color};border:1px solid {status_color};padding:.2rem .65rem;border-radius:999px;background:rgba(0,0,0,.4);">
        ● OPENROUTER: {status_text}
      </span>
      <span style="font-family:Consolas,monospace;font-size:.7rem;letter-spacing:.12em;color:#a78bfa;border:1px solid rgba(167,139,250,.4);padding:.2rem .65rem;border-radius:999px;background:rgba(0,0,0,.4);">
        MODEL: {model_name}
      </span>
      <span style="font-family:Consolas,monospace;font-size:.7rem;letter-spacing:.12em;color:#38bdf8;border:1px solid rgba(56,189,248,.4);padding:.2rem .65rem;border-radius:999px;background:rgba(0,0,0,.4);">
        RUNTIME: READY
      </span>
    </div>
  </div>
</div>
"""
