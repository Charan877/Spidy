"""Tests for BrowserVerifier and Truthful WebGL/DOM application verification."""

import pytest
from backend.verification.browser_verifier import BrowserVerifier


def test_browser_verifier_valid_web_page():
    html = """<!DOCTYPE html>
<html>
<head><title>Test App</title></head>
<body>
    <h1>Application Header</h1>
    <div id="root">
        <button id="btn">Click Me</button>
        <p>Interactive dashboard content</p>
    </div>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web")
    assert result.passed is True
    assert result.status == "PASSED"
    assert result.classification == "BROWSER_VERIFIED"
    assert result.dom_evidence.get("title") == "Test App"
    assert result.dom_evidence.get("interactive_elements_count", 0) >= 1


def test_browser_verifier_uncaught_js_exception():
    html = """<!DOCTYPE html>
<html>
<head><title>Broken App</title></head>
<body>
    <h1>Broken App</h1>
    <script>
        // Simulate broken application code
        const nonExistent = undefined;
        nonExistent.launchRocket();
    </script>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web")
    assert result.passed is False
    assert result.status == "FAILED"
    assert result.classification == "UNCAUGHT_JS_EXCEPTION"
    assert "launchRocket" in (result.error_summary or "")
    assert len(result.uncaught_exceptions) > 0


def test_browser_verifier_webgl_success():
    html = """<!DOCTYPE html>
<html>
<head><title>3D Solar System</title></head>
<body style="background: #000; margin: 0;">
    <canvas id="render-canvas" width="800" height="600"></canvas>
    <div id="hud" style="color: #fff;">Telemetry HUD</div>
    <script>
        const canvas = document.getElementById('render-canvas');
        const gl = canvas.getContext('webgl');
        gl.clearColor(0.02, 0.02, 0.05, 1.0);
        gl.clear(gl.COLOR_BUFFER_BIT);
    </script>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web_3d")
    assert result.passed is True
    assert result.status == "PASSED"
    assert result.classification == "BROWSER_VERIFIED"
    assert result.visual_evidence.get("has_canvas") is True
    assert result.visual_evidence.get("width") == 800
    assert result.visual_evidence.get("height") == 600
    assert result.visual_evidence.get("has_webgl_context") is True


def test_browser_verifier_webgl_missing_canvas():
    html = """<!DOCTYPE html>
<html>
<head><title>Fake 3D App</title></head>
<body>
    <h1>3D World</h1>
    <p>Forgot to create canvas element</p>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web_3d")
    assert result.passed is False
    assert result.status == "FAILED"
    assert result.classification == "CANVAS_NOT_FOUND"


def test_browser_verifier_webgl_zero_dimension_canvas():
    html = """<!DOCTYPE html>
<html>
<head><title>Zero Dimension Canvas</title></head>
<body>
    <canvas id="canvas" width="0" height="0" style="display:none;"></canvas>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web_3d")
    assert result.passed is False
    assert result.status == "FAILED"
    assert result.classification == "CANVAS_ZERO_DIMENSIONS"


def test_browser_verifier_empty_dom():
    html = """<!DOCTYPE html><html><head></head><body></body></html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web")
    assert result.passed is False
    assert result.status == "FAILED"
    assert result.classification == "EMPTY_DOM"


def test_browser_verifier_legitimate_dark_themed_app():
    """Ensure legitimate dark-themed apps (e.g. space/astro themes with black canvas) are verified."""
    html = """<!DOCTYPE html>
<html>
<head><title>Deep Space Simulator</title></head>
<body style="background: #000000; color: #ffffff; margin: 0;">
    <div id="hud" style="position: absolute; top: 10px; left: 10px;">
        <h1>Deep Space Navigation</h1>
        <p>Telemetry: 0 km/s</p>
        <button id="warp-btn">Engage Warp</button>
    </div>
    <canvas id="space-canvas" width="1024" height="768"></canvas>
    <script>
        const canvas = document.getElementById('space-canvas');
        const gl = canvas.getContext('webgl');
        // Clear with true pitch black
        gl.clearColor(0.0, 0.0, 0.0, 1.0);
        gl.clear(gl.COLOR_BUFFER_BIT);
        requestAnimationFrame(() => {});
    </script>
</body>
</html>"""
    url = f"data:text/html,{html}"
    result = BrowserVerifier.verify(url, app_type="web_3d")
    assert result.passed is True
    assert result.status == "PASSED"
    assert result.classification == "BROWSER_VERIFIED"
    assert result.dom_evidence.get("title") == "Deep Space Simulator"
    assert result.dom_evidence.get("interactive_elements_count") >= 1
    assert result.visual_evidence.get("has_canvas") is True
    assert result.visual_evidence.get("has_webgl_context") is True
    assert result.visual_evidence.get("gl_error") == 0
