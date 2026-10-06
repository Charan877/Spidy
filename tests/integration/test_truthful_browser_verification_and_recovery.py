import http.server
import socketserver
import threading
import time
from pathlib import Path
import pytest

from backend.core.project_state import ProjectState
from backend.verification.browser_verifier import BrowserVerifier, BrowserVerificationResult
from backend.verification.gate_evaluator import GateEvaluator
from backend.runtime.preview_manager import PreviewManager, PreviewCheckResult


class StoppableHTTPServer(socketserver.TCPServer):
    allow_reuse_address = True


def start_test_server(content_dict: dict, port: int = 18899):
    """Starts a lightweight in-memory HTTP server returning content by path."""
    class CustomHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = self.path.split("?")[0]
            if path in content_dict:
                data = content_dict[path].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/health":
                data = b'{"status": "ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = StoppableHTTPServer(("127.0.0.1", port), CustomHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)
    return server


class TestTruthfulBrowserVerificationAndRecovery:
    """Integration tests verifying that SPIDY truthfully detects broken browser apps and recovers."""

    def test_broken_webgl_app_fails_truthful_verification(self):
        """Even if HTTP responds with 200, an uncaught JS exception in WebGL must fail verification."""
        broken_html = """<!DOCTYPE html>
<html>
<head><title>Broken 3D App</title></head>
<body style="margin: 0; background: #000;">
    <canvas id="webgl-canvas" width="800" height="600"></canvas>
    <div id="hud"><h1>Loading 3D Scene...</h1></div>
    <script>
        // Fatal JS error before WebGL rendering initializes
        throw new ReferenceError("THREE is not defined: failed to import orbit controls");
    </script>
</body>
</html>"""

        port = 18891
        server = start_test_server({"/": broken_html}, port=port)
        try:
            url = f"http://127.0.0.1:{port}"
            res: BrowserVerificationResult = BrowserVerifier.verify(url, timeout_ms=5000, is_3d=True)

            assert res.passed is False
            assert res.classification in ("UNCAUGHT_JS_EXCEPTION", "CONSOLE_ERROR", "CANVAS_NOT_FOUND")
            assert any("THREE is not defined" in exc for exc in res.uncaught_exceptions)

            # Test through GateEvaluator
            state = ProjectState(goal="3D Messi Website")
            state.runtime_url = url
            state.runtime_type = "web_3d"
            preview_mgr = PreviewManager()
            check_result = PreviewCheckResult(
                is_healthy=True,
                is_app_verified=True,
                is_directory_listing=False,
                is_control_server=False,
                status_code=200,
                message="HTTP 200 OK",
                classification="APPLICATION_VERIFIED",
            )

            gate_res = GateEvaluator.evaluate_application(
                runtime_type="web_3d",
                check_result=check_result,
                workspace_dir=None,
                state=state,
                preview_manager=preview_mgr,
            )

            assert gate_res.passed is False
            assert "UNCAUGHT_JS_EXCEPTION" in gate_res.reason
        finally:
            server.shutdown()
            server.server_close()

    def test_webgl_missing_canvas_fails_truthful_verification(self):
        """A 3D application with HTTP 200 and no errors, but missing canvas must fail verification."""
        no_canvas_html = """<!DOCTYPE html>
<html>
<head><title>Empty 3D Scene</title></head>
<body style="margin: 0; background: #000;">
    <div id="container">Only text, no canvas element</div>
</body>
</html>"""

        port = 18892
        server = start_test_server({"/": no_canvas_html}, port=port)
        try:
            url = f"http://127.0.0.1:{port}"
            res: BrowserVerificationResult = BrowserVerifier.verify(url, timeout_ms=5000, is_3d=True)

            assert res.passed is False
            assert res.classification == "CANVAS_NOT_FOUND"
        finally:
            server.shutdown()
            server.server_close()

    def test_repaired_webgl_app_passes_truthful_verification(self, tmp_path):
        """Repaired WebGL application passes all checks and saves screenshot evidence."""
        working_html = """<!DOCTYPE html>
<html>
<head>
    <title>Repaired 3D App</title>
    <style>
        body { margin: 0; background: #050510; color: #fff; font-family: sans-serif; overflow: hidden; }
        #canvas3d { width: 100vw; height: 100vh; display: block; }
        #hud { position: absolute; top: 20px; left: 20px; z-index: 10; pointer-events: none; }
    </style>
</head>
<body>
    <canvas id="canvas3d" width="1024" height="768"></canvas>
    <div id="hud">
        <h1>Lionel Messi 3D Experience</h1>
        <p>8x Ballon d'Or Career Visualization</p>
    </div>
    <script>
        const canvas = document.getElementById('canvas3d');
        const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
        if (gl) {
            gl.clearColor(0.02, 0.02, 0.06, 1.0);
            gl.clear(gl.COLOR_BUFFER_BIT);
        }
        function animate() {
            if (gl) {
                gl.clear(gl.COLOR_BUFFER_BIT);
            }
            requestAnimationFrame(animate);
        }
        requestAnimationFrame(animate);
    </script>
</body>
</html>"""

        port = 18893
        server = start_test_server({"/": working_html}, port=port)
        try:
            url = f"http://127.0.0.1:{port}"
            screenshot_path = tmp_path / "messi_3d_screenshot.png"
            res: BrowserVerificationResult = BrowserVerifier.verify(
                url,
                timeout_ms=5000,
                is_3d=True,
                screenshot_path=screenshot_path,
            )

            assert res.passed is True
            assert res.classification == "BROWSER_VERIFIED"
            assert res.canvas_metrics.get("canvas_count", 0) >= 1
            assert res.canvas_metrics.get("has_webgl_context") is True
            assert res.canvas_metrics.get("active_raf") is True
            assert res.canvas_metrics.get("gl_error") == 0
            assert len(res.uncaught_exceptions) == 0
            assert screenshot_path.exists()
            assert screenshot_path.stat().st_size > 0

            # Test through GateEvaluator
            state = ProjectState(goal="3D Messi Website")
            state.runtime_url = url
            state.runtime_type = "web_3d"
            preview_mgr = PreviewManager()
            check_result = PreviewCheckResult(
                is_healthy=True,
                is_app_verified=True,
                is_directory_listing=False,
                is_control_server=False,
                status_code=200,
                message="HTTP 200 OK",
                classification="APPLICATION_VERIFIED",
            )

            gate_res = GateEvaluator.evaluate_application(
                runtime_type="web_3d",
                check_result=check_result,
                workspace_dir=None,
                state=state,
                preview_manager=preview_mgr,
            )

            assert gate_res.passed is True
            assert gate_res.status == "PASSED"
            assert gate_res.evidence.get("browser_verification", {}).get("classification") == "BROWSER_VERIFIED"
        finally:
            server.shutdown()
            server.server_close()
