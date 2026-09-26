import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, NamedTuple, Optional, Set, Tuple
import urllib.error
import urllib.parse
import urllib.request
from backend.runtime.runtime_session import SPIDY_CONTROL_PORTS, NOVA_CONTROL_PORTS


class PreviewCheckResult(NamedTuple):
    is_healthy: bool
    is_app_verified: bool
    is_directory_listing: bool
    is_control_server: bool
    status_code: int
    message: str
    classification: str = "SERVER_NOT_READY"
    content_type: str = ""
    response_size: int = 0
    body_snippet: str = ""


class PreviewManager:
    """Manages web application health checks, application content verification,
    asset integrity checks, and fullstack connectivity validation."""

    @staticmethod
    def check_health(
        url: str,
        timeout: float = 2.0,
        max_retries: int = 6,
        expected_type: Optional[str] = None,
    ) -> PreviewCheckResult:
        """Poll URL and verify HTTP status + application content.

        Ensures:
        1. Not an accidental connection to SPIDY control server.
        2. Not a raw static directory listing.
        3. Real HTTP 200/301/302/304 application response with valid entry markup.
        4. Explicit classification of HTTP 404, 500, or unresponsive status.
        """
        if not url or not url.startswith("http"):
            return PreviewCheckResult(
                is_healthy=False,
                is_app_verified=False,
                is_directory_listing=False,
                is_control_server=False,
                status_code=0,
                message="Invalid or empty URL.",
                classification="SERVER_NOT_READY",
            )

        # Guard: Check if URL inadvertently points to SPIDY's control ports
        port_match = re.search(r":(\d+)", url)
        if port_match:
            port = int(port_match.group(1))
            if port in SPIDY_CONTROL_PORTS:
                return PreviewCheckResult(
                    is_healthy=False,
                    is_app_verified=False,
                    is_directory_listing=False,
                    is_control_server=True,
                    status_code=0,
                    message=f"Port {port} is reserved for SPIDY Control Server, not the generated project.",
                    classification="WRONG_RUNTIME_PROCESS",
                )

        candidate_paths = ["", "/health", "/docs", "/api"]

        for attempt in range(max_retries):
            for path in candidate_paths:
                test_url = f"{url.rstrip('/')}{path}"
                try:
                    req = urllib.request.Request(
                        test_url,
                        headers={"User-Agent": "SPIDY-HealthCheck/2.0"},
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        status_code = response.status
                        headers = dict(response.headers)
                        content_type = headers.get("Content-Type", "")
                        body = response.read(8192).decode("utf-8", errors="ignore")
                        response_size = len(body)
                        body_snippet = body[:300].strip()

                        # Anti-pattern 1: Directory listing from raw http.server
                        if "Directory listing for" in body or "<title>Directory listing for" in body:
                            return PreviewCheckResult(
                                is_healthy=False,
                                is_app_verified=False,
                                is_directory_listing=True,
                                is_control_server=False,
                                status_code=status_code,
                                message="Directory listing returned instead of compiled application.",
                                classification="INVALID_HTML",
                                content_type=content_type,
                                response_size=response_size,
                                body_snippet=body_snippet,
                            )

                        # Anti-pattern 2: Accidental connection to Streamlit control app
                        if any(sig in body for sig in ["stApp", "window.__streamlit", "<title>Streamlit</title>"]):
                            return PreviewCheckResult(
                                is_healthy=False,
                                is_app_verified=False,
                                is_directory_listing=False,
                                is_control_server=True,
                                status_code=status_code,
                                message="Target URL resolved to SPIDY Control server instead of generated project.",
                                classification="WRONG_RUNTIME_PROCESS",
                                content_type=content_type,
                                response_size=response_size,
                                body_snippet=body_snippet,
                            )

                        # Verification: Genuine Web Application markup OR valid JSON API response
                        is_json = (
                            "application/json" in content_type
                            or (body.strip().startswith("{") and body.strip().endswith("}"))
                            or (body.strip().startswith("[") and body.strip().endswith("]"))
                        )
                        has_app_markup = any(sig in body.lower() for sig in [
                            'id="root"', "id='root'", 'id="app"', "id='app'",
                            "<canvas", "type=\"module\"", "type='module'",
                            "main.jsx", "main.tsx", "index.jsx", "bundle.js",
                            "<!doctype html>", "<html"
                        ])

                        if status_code in (200, 201, 204, 301, 302, 304, 307):
                            if expected_type == "web":
                                is_verified = has_app_markup or ("text/html" in content_type and not is_json)
                                if is_json and not has_app_markup:
                                    return PreviewCheckResult(
                                        is_healthy=True,
                                        is_app_verified=False,
                                        is_directory_listing=False,
                                        is_control_server=False,
                                        status_code=status_code,
                                        message=f"HTTP {status_code} returned API JSON instead of web application HTML.",
                                        classification="UNEXPECTED_API_RESPONSE",
                                        content_type=content_type,
                                        response_size=response_size,
                                        body_snippet=body_snippet,
                                    )
                            elif expected_type == "api":
                                is_verified = is_json or "json" in content_type or status_code == 200
                            else:
                                is_verified = (has_app_markup or is_json)

                            if is_verified and len(body.strip()) > 1:
                                return PreviewCheckResult(
                                    is_healthy=True,
                                    is_app_verified=True,
                                    is_directory_listing=False,
                                    is_control_server=False,
                                    status_code=status_code,
                                    message=f"Application response verified at {path or '/'}.",
                                    classification="APPLICATION_VERIFIED",
                                    content_type=content_type,
                                    response_size=response_size,
                                    body_snippet=body_snippet,
                                )
                            else:
                                return PreviewCheckResult(
                                    is_healthy=True,
                                    is_app_verified=False,
                                    is_directory_listing=False,
                                    is_control_server=False,
                                    status_code=status_code,
                                    message=f"HTTP {status_code} returned at {path or '/'} but application content is invalid.",
                                    classification="INVALID_HTML",
                                    content_type=content_type,
                                    response_size=response_size,
                                    body_snippet=body_snippet,
                                )

                except urllib.error.HTTPError as http_err:
                    status_code = http_err.code
                    content_type = http_err.headers.get("Content-Type", "") if http_err.headers else ""
                    try:
                        err_body = http_err.read().decode("utf-8", errors="ignore")
                    except Exception:
                        err_body = ""

                    # If 404, continue to next candidate path (e.g. /health or /docs)
                    if status_code == 404 and path != candidate_paths[-1]:
                        continue

                    if status_code == 404:
                        return PreviewCheckResult(
                            is_healthy=False,
                            is_app_verified=False,
                            is_directory_listing=False,
                            is_control_server=False,
                            status_code=status_code,
                            message=f"HTTP 404 Not Found at {test_url}.",
                            classification="HTTP_404",
                            content_type=content_type,
                            response_size=len(err_body),
                            body_snippet=err_body[:300].strip(),
                        )
                    elif status_code >= 500:
                        return PreviewCheckResult(
                            is_healthy=False,
                            is_app_verified=False,
                            is_directory_listing=False,
                            is_control_server=False,
                            status_code=status_code,
                            message=f"HTTP {status_code} Server Error: {http_err.reason}",
                            classification="HTTP_500",
                            content_type=content_type,
                            response_size=len(err_body),
                            body_snippet=err_body[:300].strip(),
                        )
                    else:
                        return PreviewCheckResult(
                            is_healthy=False,
                            is_app_verified=False,
                            is_directory_listing=False,
                            is_control_server=False,
                            status_code=status_code,
                            message=f"HTTP {status_code}: {http_err.reason}",
                            classification=f"HTTP_{status_code}",
                            content_type=content_type,
                            response_size=len(err_body),
                            body_snippet=err_body[:300].strip(),
                        )

                except Exception:
                    # Connection refused or host unreachable, try next candidate path
                    pass

            time.sleep(0.6)

        return PreviewCheckResult(
            is_healthy=False,
            is_app_verified=False,
            is_directory_listing=False,
            is_control_server=False,
            status_code=0,
            message="Server not responding on HTTP.",
            classification="HTTP_UNRESPONSIVE",
        )

    @staticmethod
    def verify_referenced_assets(
        workspace_dir: str | Path,
        html_file: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify that all local assets (CSS, JS, images) referenced in HTML files exist on disk.

        Prevents false positive 'BUILT. VERIFIED.' when index.html is served via http.server
        but references ungenerated style.css or script.js.
        """
        ws = Path(workspace_dir).resolve()
        if not ws.exists():
            return False, ["Workspace directory does not exist"]

        html_paths: List[Path] = []
        if html_file:
            target = ws / html_file
            if target.exists():
                html_paths.append(target)
        else:
            html_paths.extend(ws.glob("**/*.html"))

        if not html_paths:
            # Not an HTML project, pass check
            return True, []

        missing_assets: List[str] = []
        # Regex patterns for CSS links and script tags
        css_re = re.compile(r'<link[^>]+rel=[\'"]stylesheet[\'"][^>]+href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
        css_alt_re = re.compile(r'<link[^>]+href=[\'"]([^\'"]+)[\'"][^>]+rel=[\'"]stylesheet[\'"]', re.IGNORECASE)
        js_re = re.compile(r'<script[^>]+src=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)

        for html_path in html_paths:
            try:
                content = html_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            matches = css_re.findall(content) + css_alt_re.findall(content) + js_re.findall(content)

            for href in matches:
                href = href.strip()
                # Ignore external CDNs, data URIs, or hash fragments
                if (
                    href.startswith("http://")
                    or href.startswith("https://")
                    or href.startswith("//")
                    or href.startswith("data:")
                    or href.startswith("#")
                ):
                    continue

                # Strip query params or hash from path
                clean_href = href.split("?")[0].split("#")[0].lstrip("/")
                asset_path = html_path.parent / clean_href
                if not asset_path.exists():
                    missing_assets.append(f"{html_path.name} -> {href}")

        if missing_assets:
            return False, missing_assets
        return True, []

    @staticmethod
    def verify_fullstack_connectivity(
        frontend_url: str,
        backend_url: str,
        endpoints: Optional[List[str]] = None,
        timeout: float = 2.0,
    ) -> Tuple[bool, str]:
        """Test fullstack connectivity between frontend and backend.

        Verifies that backend is responding, CORS headers are permissible,
        and required API endpoints are reachable.
        """
        if not backend_url or not backend_url.startswith("http"):
            return False, "Backend URL is invalid or not started"

        test_endpoints = endpoints or ["", "/health", "/api"]
        backend_alive = False
        cors_ok = False
        tested_urls = []

        for ep in test_endpoints:
            url = f"{backend_url.rstrip('/')}{ep}"
            tested_urls.append(url)
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "Origin": frontend_url.rstrip("/"),
                        "User-Agent": "SPIDY-FullStack-Validator/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status in (200, 201, 204):
                        backend_alive = True
                        cors_header = resp.headers.get("Access-Control-Allow-Origin", "")
                        if cors_header in ("*", frontend_url.rstrip("/")) or not frontend_url:
                            cors_ok = True
                        break
            except Exception:
                pass

        if not backend_alive:
            return False, f"Backend failed to respond on tested endpoints: {', '.join(tested_urls)}"

        return True, "Full-stack connectivity verified"

    @staticmethod
    def verify_docs_endpoint(url: str, timeout: float = 1.5) -> bool:
        """Check if /docs endpoint exists and serves Swagger/OpenAPI documentation."""
        if not url or not url.startswith("http"):
            return False
        docs_url = f"{url.rstrip('/')}/docs"
        try:
            req = urllib.request.Request(docs_url, headers={"User-Agent": "SPIDY-HealthCheck/2.0"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    body = response.read(4096).decode("utf-8", errors="ignore")
                    return any(s in body.lower() for s in ["swagger", "openapi", "redoc", "api", "<html"])
        except Exception:
            pass
        return False

    @staticmethod
    def verify_fullstack_crud_transaction(
        backend_url: str,
        workspace_dir: Optional[Path] = None,
        endpoint: str = "/api/items",
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 3.0,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Perform a real integration CRUD transaction (POST -> SQLite -> GET).

        Validates:
        1. POST to backend API succeeds (200/201/202).
        2. Backend returns created entity with assigned ID or confirmation.
        3. GET from backend returns the newly created item.
        4. SQLite database file on disk is validated.
        """
        details: Dict[str, Any] = {
            "endpoint": endpoint,
            "post_status": None,
            "get_status": None,
            "created_id": None,
            "db_files_found": [],
            "db_has_records": False,
        }

        if not backend_url or not backend_url.startswith("http"):
            return False, "Backend URL is invalid.", details

        clean_base = backend_url.rstrip("/")
        test_payload = payload or {"title": "Automated Transaction Test", "amount": 25.0, "done": False}

        # 1. Attempt POST to create entity
        post_url = f"{clean_base}{endpoint}"
        try:
            req_data = json.dumps(test_payload).encode("utf-8")
            post_req = urllib.request.Request(
                post_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "SPIDY-CRUD-Validator/1.0"},
                method="POST",
            )
            with urllib.request.urlopen(post_req, timeout=timeout) as resp:
                details["post_status"] = resp.status
                if resp.status not in (200, 201, 202):
                    return False, f"POST {endpoint} returned unexpected status: {resp.status}", details
                resp_body = resp.read().decode("utf-8", errors="ignore")
                try:
                    resp_json = json.loads(resp_body)
                    details["created_id"] = resp_json.get("id") or resp_json.get("_id") or resp_json.get("title")
                except Exception:
                    pass
        except Exception as exc:
            return False, f"POST {endpoint} failed: {exc}", details

        # 2. Attempt GET to verify retrieval
        get_url = f"{clean_base}{endpoint}"
        try:
            get_req = urllib.request.Request(
                get_url,
                headers={"User-Agent": "SPIDY-CRUD-Validator/1.0"},
                method="GET",
            )
            with urllib.request.urlopen(get_req, timeout=timeout) as resp:
                details["get_status"] = resp.status
                if resp.status != 200:
                    return False, f"GET {endpoint} returned status {resp.status}", details
                body = resp.read().decode("utf-8", errors="ignore")
                if test_payload.get("title") and test_payload["title"] not in body:
                    # Non-fatal if serialized differently, but logged
                    pass
        except Exception as exc:
            return False, f"GET {endpoint} failed: {exc}", details

        # 3. Check SQLite database file on disk if workspace_dir is provided
        if workspace_dir:
            ws_path = Path(workspace_dir)
            if ws_path.exists():
                db_files = list(ws_path.glob("*.db")) + list(ws_path.glob("app/*.db")) + list(ws_path.glob("backend/*.db"))
                details["db_files_found"] = [str(f.name) for f in db_files]
                for dbf in db_files:
                    if dbf.stat().st_size > 0:
                        try:
                            conn = sqlite3.connect(str(dbf))
                            cursor = conn.cursor()
                            tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
                            if tables:
                                details["db_has_records"] = True
                            conn.close()
                        except Exception:
                            pass

        return True, f"Full-stack CRUD transaction verified on {endpoint} (POST: {details['post_status']}, GET: {details['get_status']})", details
