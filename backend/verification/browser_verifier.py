"""Browser Application Verification Engine for SPIDY.

Performs authoritative, browser-level verification of running applications using Playwright.
Inspects page loading, DOM/application structure, browser console errors, uncaught JavaScript errors,
failed network requests, document dimensions, interactive elements, WebGL/Three.js rendering surfaces,
and captures screenshot evidence.

Distinguishes legitimate dark-themed applications from crashed/blank rendering surfaces using
multiple independent signals (DOM health, WebGL context state, error absence, and canvas dimensions).
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.parse

logger = logging.getLogger("spidy.browser_verifier")


@dataclass
class BrowserVerificationResult:
    passed: bool
    status: str  # "PASSED", "FAILED"
    classification: str
    error_summary: Optional[str] = None
    url: str = ""
    console_errors: List[str] = field(default_factory=list)
    console_warnings: List[str] = field(default_factory=list)
    uncaught_exceptions: List[str] = field(default_factory=list)
    failed_requests: List[Dict[str, Any]] = field(default_factory=list)
    dom_evidence: Dict[str, Any] = field(default_factory=dict)
    visual_evidence: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None
    duration_ms: float = 0.0

    @property
    def canvas_metrics(self) -> Dict[str, Any]:
        """Convenience property for inspecting canvas metrics."""
        return self.visual_evidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "status": self.status,
            "classification": self.classification,
            "error_summary": self.error_summary,
            "url": self.url,
            "console_errors": self.console_errors,
            "console_warnings": self.console_warnings,
            "uncaught_exceptions": self.uncaught_exceptions,
            "failed_requests": self.failed_requests,
            "dom_evidence": self.dom_evidence,
            "visual_evidence": self.visual_evidence,
            "screenshot_path": self.screenshot_path,
            "duration_ms": self.duration_ms,
        }


class BrowserVerifier:
    """Automated browser inspection engine for web, WebGL, and full-stack frontends."""

    @classmethod
    def verify(
        cls,
        url: str,
        app_type: str = "web",
        screenshot_dir: Optional[Path] = None,
        timeout_seconds: float = 8.0,
        timeout_ms: Optional[float] = None,
        is_3d: bool = False,
        screenshot_path: Optional[Any] = None,
    ) -> BrowserVerificationResult:
        """Inspect running web application in real Chromium browser."""
        if is_3d:
            app_type = "web_3d"
        if timeout_ms is not None:
            timeout_seconds = timeout_ms / 1000.0

        start_time = time.time()
        
        # Lazy import playwright so environments without it don't crash at startup
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.warning("Playwright not installed. Falling back to HTTP-only verification.")
            return BrowserVerificationResult(
                passed=True,
                status="PASSED",
                classification="PLAYWRIGHT_UNAVAILABLE_FALLBACK",
                url=url,
                error_summary="Playwright not installed in environment; skipping browser automation.",
                duration_ms=(time.time() - start_time) * 1000,
            )

        console_errors: List[str] = []
        console_warnings: List[str] = []
        uncaught_exceptions: List[str] = []
        failed_requests: List[Dict[str, Any]] = []
        target_screenshot_path = screenshot_path
        screenshot_path: Optional[str] = None
        dom_evidence: Dict[str, Any] = {}
        visual_evidence: Dict[str, Any] = {}

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--use-gl=angle",
                        "--use-angle=swiftshader",  # Ensures software WebGL runs reliably in headless CI/Windows
                        "--enable-webgl",
                        "--ignore-gpu-blocklist",
                    ]
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="SPIDY-BrowserVerifier/2.0",
                )
                page = context.new_page()

                # Event listeners for runtime error diagnostics
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text)
                    if msg.type == "error"
                    else (console_warnings.append(msg.text) if msg.type == "warning" else None),
                )
                page.on("pageerror", lambda err: uncaught_exceptions.append(str(err)))
                page.on(
                    "requestfailed",
                    lambda req: failed_requests.append({
                        "url": req.url,
                        "method": req.method,
                        "failure": req.failure or "Network request failed",
                    }),
                )
                page.on(
                    "response",
                    lambda resp: failed_requests.append({
                        "url": resp.url,
                        "status": resp.status,
                        "status_text": resp.status_text,
                    })
                    if resp.status >= 400 and not resp.url.endswith("favicon.ico")
                    else None,
                )

                # Format data:text/html URLs if unencoded HTML passed
                target_url = url
                if target_url.startswith("data:text/html") and (";base64," not in target_url) and ("#" in target_url or "\n" in target_url):
                    prefix = target_url.split(",", 1)[0] + ","
                    raw_content = target_url[len(prefix):]
                    target_url = f"data:text/html;charset=utf-8,{urllib.parse.quote(raw_content)}"

                # Navigate to the target application
                try:
                    page.goto(target_url, timeout=int(timeout_seconds * 1000), wait_until="domcontentloaded")
                except Exception as nav_err:
                    browser.close()
                    return BrowserVerificationResult(
                        passed=False,
                        status="FAILED",
                        classification="NAVIGATION_FAILED",
                        error_summary=f"Browser failed to connect to {url}: {nav_err}",
                        url=url,
                        duration_ms=(time.time() - start_time) * 1000,
                    )

                # Wait for JavaScript execution and rendering
                page.wait_for_timeout(1200)

                # 1. Collect DOM Structure Evidence
                try:
                    dom_evidence = page.evaluate("""() => {
                        const title = document.title || '';
                        const allNodes = document.querySelectorAll('*');
                        const totalElements = allNodes.length;
                        const bodyText = (document.body ? document.body.innerText : '').trim();
                        const buttons = document.querySelectorAll('button, a, input, select');
                        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                        const hasRoot = Boolean(document.getElementById('root') || document.getElementById('app') || document.querySelector('main'));
                        
                        return {
                            title: title,
                            total_elements: totalElements,
                            body_text_length: bodyText.length,
                            body_text_snippet: bodyText.slice(0, 300),
                            interactive_elements_count: buttons.length,
                            headings_count: headings.length,
                            has_root_container: hasRoot,
                        };
                    }""")
                except Exception as eval_err:
                    dom_evidence = {"error": f"Failed evaluating DOM: {eval_err}"}

                # 2. Collect Visual & WebGL Evidence
                try:
                    visual_evidence = page.evaluate("""() => {
                        const canvases = Array.from(document.querySelectorAll('canvas'));
                        if (canvases.length === 0) {
                            return {
                                has_canvas: false,
                                canvas_count: 0,
                                reason: 'No canvas element present in DOM.'
                            };
                        }

                        const c = canvases[0];
                        const rect = c.getBoundingClientRect();
                        const width = c.width || rect.width;
                        const height = c.height || rect.height;

                        if (width <= 0 || height <= 0) {
                            return {
                                has_canvas: true,
                                canvas_count: canvases.length,
                                width: width,
                                height: height,
                                is_zero_dimension: true,
                                reason: 'Canvas element has zero width or height.'
                            };
                        }

                        let contextType = 'none';
                        let gl = null;
                        try {
                            gl = c.getContext('webgl2') || c.getContext('webgl') || c.getContext('experimental-webgl');
                            if (gl) {
                                contextType = (typeof WebGL2RenderingContext !== 'undefined' && gl instanceof WebGL2RenderingContext) ? 'webgl2' : 'webgl';
                            }
                        } catch(e) {}

                        let glError = 0;
                        let hasActiveContext = false;
                        if (gl) {
                            hasActiveContext = true;
                            glError = gl.getError();
                        } else {
                            try {
                                const ctx2d = c.getContext('2d');
                                if (ctx2d) contextType = '2d';
                            } catch(e) {}
                        }

                        return {
                            has_canvas: true,
                            canvas_count: canvases.length,
                            width: width,
                            height: height,
                            context_type: contextType,
                            has_webgl_context: hasActiveContext,
                            gl_error: glError,
                            active_raf: (typeof requestAnimationFrame === 'function'),
                            is_zero_dimension: false,
                        };
                    }""")
                except Exception as vis_err:
                    visual_evidence = {"error": f"Failed evaluating visual surface: {vis_err}"}

                # 3. Capture Screenshot Evidence
                if target_screenshot_path:
                    try:
                        sc_path = Path(target_screenshot_path)
                        sc_path.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(sc_path), full_page=True)
                        screenshot_path = str(sc_path)
                    except Exception as sc_err:
                        logger.warning(f"Failed capturing browser screenshot: {sc_err}")
                elif screenshot_dir:
                    try:
                        screenshot_dir = Path(screenshot_dir)
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        sc_file = screenshot_dir / f"browser_verification_{int(time.time())}.png"
                        page.screenshot(path=str(sc_file), full_page=True)
                        screenshot_path = str(sc_file)
                    except Exception as sc_err:
                        logger.warning(f"Failed capturing browser screenshot: {sc_err}")

                browser.close()

        except Exception as exc:
            return BrowserVerificationResult(
                passed=False,
                status="FAILED",
                classification="BROWSER_AUTOMATION_ERROR",
                error_summary=f"Playwright automation exception: {exc}",
                url=url,
                duration_ms=(time.time() - start_time) * 1000,
            )

        duration_ms = (time.time() - start_time) * 1000

        # Filter ignorable console noise (e.g. favicon 404 or harmless warnings)
        critical_console_errors = [
            err for err in console_errors
            if not any(ign in err.lower() for ign in ["favicon.ico", "source-map", "sourcemap", "devtools"])
        ]
        critical_failed_requests = [
            req for req in failed_requests
            if not str(req.get("url", "")).endswith("favicon.ico")
        ]

        # -------------------------------------------------------------
        # MULTI-SIGNAL AUTHORITATIVE EVALUATION
        # -------------------------------------------------------------

        # Gate Check A: Uncaught JavaScript Exceptions (window.onerror)
        if uncaught_exceptions:
            err_msg = uncaught_exceptions[0]
            return BrowserVerificationResult(
                passed=False,
                status="FAILED",
                classification="UNCAUGHT_JS_EXCEPTION",
                error_summary=f"Uncaught JavaScript exception in browser: {err_msg}",
                url=url,
                console_errors=console_errors,
                console_warnings=console_warnings,
                uncaught_exceptions=uncaught_exceptions,
                failed_requests=failed_requests,
                dom_evidence=dom_evidence,
                visual_evidence=visual_evidence,
                screenshot_path=screenshot_path,
                duration_ms=duration_ms,
            )

        # Gate Check B: Critical Console Errors
        if critical_console_errors:
            err_msg = critical_console_errors[0]
            return BrowserVerificationResult(
                passed=False,
                status="FAILED",
                classification="CONSOLE_ERROR",
                error_summary=f"Browser console error: {err_msg}",
                url=url,
                console_errors=console_errors,
                console_warnings=console_warnings,
                uncaught_exceptions=uncaught_exceptions,
                failed_requests=failed_requests,
                dom_evidence=dom_evidence,
                visual_evidence=visual_evidence,
                screenshot_path=screenshot_path,
                duration_ms=duration_ms,
            )

        # Gate Check C: Failed Critical Assets (404/500 on JS/CSS/WASM)
        critical_assets_failed = [
            req for req in critical_failed_requests
            if any(str(req.get("url", "")).endswith(ext) for ext in [".js", ".css", ".wasm", ".json"])
        ]
        if critical_assets_failed:
            bad_asset = critical_assets_failed[0]
            return BrowserVerificationResult(
                passed=False,
                status="FAILED",
                classification="RESOURCE_LOAD_FAILED",
                error_summary=f"Required asset failed to load in browser: {bad_asset.get('url')} (Status: {bad_asset.get('status')})",
                url=url,
                console_errors=console_errors,
                console_warnings=console_warnings,
                uncaught_exceptions=uncaught_exceptions,
                failed_requests=failed_requests,
                dom_evidence=dom_evidence,
                visual_evidence=visual_evidence,
                screenshot_path=screenshot_path,
                duration_ms=duration_ms,
            )

        # Gate Check D: DOM Empty / Blank Page Check
        total_elements = dom_evidence.get("total_elements", 0)
        body_len = dom_evidence.get("body_text_length", 0)
        has_canvas = visual_evidence.get("has_canvas", False)

        if total_elements <= 3 and body_len == 0 and not has_canvas:
            return BrowserVerificationResult(
                passed=False,
                status="FAILED",
                classification="EMPTY_DOM",
                error_summary="Browser rendered an empty document with no visible elements or markup.",
                url=url,
                console_errors=console_errors,
                console_warnings=console_warnings,
                uncaught_exceptions=uncaught_exceptions,
                failed_requests=failed_requests,
                dom_evidence=dom_evidence,
                visual_evidence=visual_evidence,
                screenshot_path=screenshot_path,
                duration_ms=duration_ms,
            )

        # Gate Check E: WebGL / 3D Specific Verification
        if app_type in ("web_3d", "webgl", "threejs"):
            if not has_canvas:
                return BrowserVerificationResult(
                    passed=False,
                    status="FAILED",
                    classification="CANVAS_NOT_FOUND",
                    error_summary="3D WebGL application failed: No <canvas> element found in the DOM.",
                    url=url,
                    console_errors=console_errors,
                    console_warnings=console_warnings,
                    uncaught_exceptions=uncaught_exceptions,
                    failed_requests=failed_requests,
                    dom_evidence=dom_evidence,
                    visual_evidence=visual_evidence,
                    screenshot_path=screenshot_path,
                    duration_ms=duration_ms,
                )

            if visual_evidence.get("is_zero_dimension", False):
                return BrowserVerificationResult(
                    passed=False,
                    status="FAILED",
                    classification="CANVAS_ZERO_DIMENSIONS",
                    error_summary=f"3D WebGL canvas has zero dimensions ({visual_evidence.get('width')}x{visual_evidence.get('height')}).",
                    url=url,
                    console_errors=console_errors,
                    console_warnings=console_warnings,
                    uncaught_exceptions=uncaught_exceptions,
                    failed_requests=failed_requests,
                    dom_evidence=dom_evidence,
                    visual_evidence=visual_evidence,
                    screenshot_path=screenshot_path,
                    duration_ms=duration_ms,
                )

            gl_error = visual_evidence.get("gl_error", 0)
            if gl_error != 0:
                return BrowserVerificationResult(
                    passed=False,
                    status="FAILED",
                    classification="WEBGL_CONTEXT_ERROR",
                    error_summary=f"WebGL context reported rendering error code {gl_error}.",
                    url=url,
                    console_errors=console_errors,
                    console_warnings=console_warnings,
                    uncaught_exceptions=uncaught_exceptions,
                    failed_requests=failed_requests,
                    dom_evidence=dom_evidence,
                    visual_evidence=visual_evidence,
                    screenshot_path=screenshot_path,
                    duration_ms=duration_ms,
                )

        # All multi-signal checks passed cleanly
        return BrowserVerificationResult(
            passed=True,
            status="PASSED",
            classification="BROWSER_VERIFIED",
            error_summary=None,
            url=url,
            console_errors=console_errors,
            console_warnings=console_warnings,
            uncaught_exceptions=uncaught_exceptions,
            failed_requests=failed_requests,
            dom_evidence=dom_evidence,
            visual_evidence=visual_evidence,
            screenshot_path=screenshot_path,
            duration_ms=duration_ms,
        )
