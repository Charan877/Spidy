"""Environment Detector for NOVA Code Lab.

Inspects workspace files to determine the project type, programming language,
framework, dependencies, and safe local runtime command.
Prioritizes project metadata files (package.json, pyproject.toml, Cargo.toml)
over raw static file extensions.
Guarantees complete isolation from NOVA's Streamlit control ports (8500-8502).
"""

import json
import os
from pathlib import Path
import re
import socket
import sys
from typing import Dict, List, Optional
from backend.core.workspace_manager import WorkspaceManager
from backend.runtime.runtime_session import NOVA_CONTROL_PORTS


def find_free_port(start_port: int = 9000, max_port: int = 9999) -> int:
    """Find a free TCP port on localhost in the 9000+ range (isolated from NOVA control ports)."""
    from backend.runtime.process_manager import get_port_owner_pid

    for port in range(start_port, max_port):
        if port in NOVA_CONTROL_PORTS:
            continue
        if get_port_owner_pid(port) is not None:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sys.platform == "win32" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except Exception:
                    pass
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port


def inspect_vite_structure(workspace: WorkspaceManager) -> Dict:
    """Inspect Vite project root, config, and index.html location."""
    root = getattr(workspace, "root", None)
    if root is None or not isinstance(root, Path):
        root = Path(".")
    has_root_index = (root / "index.html").exists()

    vite_config_file = None
    for cfg in ["vite.config.ts", "vite.config.js", "vite.config.mjs"]:
        if (root / cfg).exists():
            vite_config_file = cfg
            break

    custom_root = None
    if vite_config_file:
        try:
            cfg_text = (root / vite_config_file).read_text(encoding="utf-8")
            m = re.search(r"root\s*:\s*['\"]([^'\"]+)['\"]", cfg_text)
            if m:
                custom_root = m.group(1)
        except Exception:
            pass

    alt_index_location = None
    for alt in ["public/index.html", "src/index.html"]:
        if (root / alt).exists():
            alt_index_location = alt
            break

    effective_root = str((root / custom_root).resolve()) if custom_root else str(root)
    effective_index_exists = (Path(effective_root) / "index.html").exists()

    return {
        "has_root_index": has_root_index,
        "vite_config_file": vite_config_file,
        "custom_root": custom_root,
        "effective_root": effective_root,
        "effective_index_exists": effective_index_exists,
        "alt_index_location": alt_index_location,
    }


class EnvironmentDetector:
    """Detects runtime configuration for project workspace using metadata-first inspection."""

    @staticmethod
    def inspect_vite_structure(workspace: WorkspaceManager) -> Dict:
        return inspect_vite_structure(workspace)

    @staticmethod
    def detect(workspace: WorkspaceManager, override_language: str = "Auto Detect") -> Dict:
        """Inspect workspace files and return runtime config dict."""
        files = workspace.list_files()
        all_contents = workspace.load_all_files()

        ws_root = getattr(workspace, "root", None)
        if ws_root is None or not isinstance(ws_root, Path):
            try:
                ws_root = Path(str(ws_root)) if ws_root is not None and not str(ws_root).startswith("<MagicMock") else Path(".")
            except Exception:
                ws_root = Path(".")

        python_exe = sys.executable
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"

        # 1. Inspect package.json FIRST (Node.js / React / Vite / Next.js)
        pkg_file = None
        if "package.json" in files:
            pkg_file = "package.json"
        else:
            for f in files:
                if f.endswith("package.json"):
                    pkg_file = f
                    break

        if pkg_file:
            pkg_content = all_contents.get(pkg_file, "{}")
            try:
                pkg_data = json.loads(pkg_content)
            except Exception:
                pkg_data = {}

            scripts = pkg_data.get("scripts", {})
            dependencies = pkg_data.get("dependencies", {})
            dev_dependencies = pkg_data.get("devDependencies", {})
            all_deps = {**dependencies, **dev_dependencies}

            # Precise multi-factor framework detection
            is_ts = (
                "typescript" in all_deps
                or any(f.endswith(".ts") or f.endswith(".tsx") for f in files)
                or any("tsconfig" in f for f in files)
            )
            is_three = (
                "three" in all_deps
                or "@react-three/fiber" in all_deps
                or "@react-three/drei" in all_deps
                or "@types/three" in all_deps
                or any("three" in c.lower() for c in all_contents.values())
            )
            is_vite = (
                "vite" in all_deps
                or any("vite.config" in f for f in files)
                or any("vite" in str(s) for s in scripts.values())
            )

            # Construct accurate framework name
            if "next" in all_deps:
                framework = "Next.js + TypeScript Web App" if is_ts else "Next.js Web App"
            elif "react" in all_deps:
                parts = ["React"]
                if is_ts:
                    parts.append("TypeScript")
                if is_vite:
                    parts.append("Vite")
                if is_three:
                    parts.append("Three.js")
                parts.append("Web App")
                framework = " + ".join(parts[:-1]) + " " + parts[-1]
            elif "vue" in all_deps:
                parts = ["Vue"]
                if is_ts:
                    parts.append("TypeScript")
                if is_vite:
                    parts.append("Vite")
                parts.append("Web App")
                framework = " + ".join(parts[:-1]) + " " + parts[-1]
            elif "svelte" in all_deps or "@sveltejs/kit" in all_deps:
                framework = "Svelte Web App"
            elif is_vite:
                parts = ["Vite"]
                if is_ts:
                    parts.append("TypeScript")
                if is_three:
                    parts.append("Three.js")
                parts.append("Web App")
                framework = " + ".join(parts[:-1]) + " " + parts[-1]
            elif "express" in all_deps:
                framework = "Express.js REST API"
            elif "fastify" in all_deps:
                framework = "Fastify REST API"
            elif "@nestjs/core" in all_deps:
                framework = "NestJS Application"
            else:
                framework = "Node.js Application"

            # Determine best script command from actual package.json scripts
            script_name = None
            for candidate in ["dev", "start", "serve", "preview"]:
                if candidate in scripts:
                    script_name = candidate
                    break

            # Working directory calculation
            pkg_rel_dir = Path(pkg_file).parent
            project_root_dir = (ws_root / pkg_rel_dir).resolve()

            has_node_modules = (project_root_dir / "node_modules").exists()

            if script_name:
                cmd = [npm_cmd, "run", script_name]
            elif "start" in scripts:
                cmd = [npm_cmd, "start"]
            elif is_vite:
                npx_cmd = "npx.cmd" if sys.platform == "win32" else "npx"
                cmd = [npx_cmd, "vite"]
            else:
                cmd = [npm_cmd, "start"]

            # Check Vite project structure & entry point
            vite_info = {}
            missing_index = False
            if is_vite:
                vite_info = inspect_vite_structure(workspace)
                missing_index = not (project_root_dir / "index.html").exists()

            # Determine runtime_type
            is_node_api = any(api_pkg in all_deps for api_pkg in ["express", "fastify", "@nestjs/core"])
            runtime_type = "api" if is_node_api else "web"

            # Check for full-stack workspace (e.g. Node frontend + Python backend)
            has_py_backend = any(
                f.endswith(".py") and any(b in all_contents.get(f, "") for b in ["FastAPI", "Flask", "uvicorn"])
                for f in files
            )
            if has_py_backend and not is_node_api:
                runtime_type = "fullstack"

            return {
                "project_type": framework,
                "runtime_type": runtime_type,
                "is_web": True,
                "port": None,
                "url": None,
                "command": cmd,
                "cwd": str(project_root_dir),
                "main_file": pkg_file,
                "requires_install": not has_node_modules,
                "install_command": [npm_cmd, "install"],
                "has_dev_server": True,
                "missing_index": missing_index,
                "vite_info": vite_info,
                "has_docs": False,
            }

        # 2. Inspect Streamlit Web App (assign isolated port in 8600+ range, never 8501/8500)
        for fname, content in all_contents.items():
            if fname.endswith(".py") and ("streamlit" in content or "st.set_page_config" in content):
                target_path = str(ws_root / fname)
                isolated_port = find_free_port(start_port=8600, max_port=8699)
                return {
                    "project_type": "Streamlit Web App",
                    "runtime_type": "web",
                    "is_web": True,
                    "port": isolated_port,
                    "url": f"http://localhost:{isolated_port}",
                    "command": [
                        python_exe,
                        "-m",
                        "streamlit",
                        "run",
                        target_path,
                        "--server.port",
                        str(isolated_port),
                        "--server.headless",
                        "true",
                    ],
                    "cwd": str(ws_root),
                    "main_file": fname,
                    "requires_install": False,
                    "install_command": [],
                    "has_dev_server": True,
                    "has_docs": False,
                }

        # 3. Inspect Python Web API (Flask / FastAPI)
        for fname, content in all_contents.items():
            if fname.endswith(".py") and ("Flask" in content or "FastAPI" in content or "uvicorn" in content):
                isolated_port = find_free_port(start_port=9000, max_port=9999)
                stem = Path(fname).stem
                has_reqs = "requirements.txt" in files
                install_cmd = [python_exe, "-m", "pip", "install", "-r", str(ws_root / "requirements.txt")] if has_reqs else []

                # Framework-specific startup command selection
                mod_path = str(Path(fname).with_suffix("")).replace("/", ".").replace("\\", ".")
                if "FastAPI" in content:
                    framework_type = "FastAPI Web Service"
                    app_match = re.search(r"\b(\w+)\s*=\s*FastAPI\s*\(", content)
                    app_var = app_match.group(1) if app_match else "app"
                    # Canonical ASGI runner with explicit host & isolated port
                    cmd = [python_exe, "-m", "uvicorn", f"{mod_path}:{app_var}", "--host", "127.0.0.1", "--port", str(isolated_port)]
                elif "Flask" in content:
                    framework_type = "Flask Web Service"
                    if "app.run" in content:
                        cmd = [python_exe, str(ws_root / fname)]
                    else:
                        cmd = [python_exe, "-m", "flask", "--app", mod_path, "run", "--host", "127.0.0.1", "--port", str(isolated_port)]
                else:
                    framework_type = "Python Web API"
                    cmd = [python_exe, str(ws_root / fname)]

                has_docs = ("FastAPI" in content)
                has_web_frontend = any(f.endswith("package.json") or f.endswith("index.html") for f in files)
                runtime_type = "fullstack" if has_web_frontend else "api"

                frontend_config = None
                if has_web_frontend:
                    web_index = None
                    for candidate in ["index.html", "public/index.html", "frontend/index.html", "src/index.html"]:
                        if candidate in files:
                            web_index = candidate
                            break
                    if web_index:
                        fe_port = find_free_port(start_port=8080, max_port=8999)
                        fe_dir = str((ws_root / Path(web_index).parent).resolve())
                        frontend_config = {
                            "project_type": "HTML / Web Frontend",
                            "runtime_type": "web",
                            "is_web": True,
                            "port": fe_port,
                            "url": f"http://localhost:{fe_port}",
                            "command": [python_exe, "-m", "http.server", str(fe_port)],
                            "cwd": fe_dir,
                            "main_file": web_index,
                        }

                return {
                    "project_type": framework_type,
                    "runtime_type": runtime_type,
                    "is_web": True,
                    "port": isolated_port,
                    "url": f"http://localhost:{isolated_port}",
                    "command": cmd,
                    "cwd": str(ws_root),
                    "main_file": fname,
                    "requires_install": has_reqs,
                    "install_command": install_cmd,
                    "has_dev_server": True,
                    "has_docs": has_docs,
                    "docs_path": "/docs" if has_docs else None,
                    "backend_port": isolated_port if has_web_frontend else None,
                    "frontend_config": frontend_config,
                }

        # 4. HTML / 3D WebGL / Static Web Projects (ONLY if no dev server metadata exists)
        web_index = None
        for candidate in ["index.html", "public/index.html", "frontend/index.html", "src/index.html"]:
            if candidate in files:
                web_index = candidate
                break

        if web_index:
            target_dir = str((ws_root / Path(web_index).parent).resolve())
            isolated_port = find_free_port(start_port=9000, max_port=9999)
            return {
                "project_type": "HTML / 3D WebGL Application",
                "runtime_type": "web",
                "is_web": True,
                "port": isolated_port,
                "url": f"http://localhost:{isolated_port}",
                "command": [python_exe, "-m", "http.server", str(isolated_port)],
                "cwd": target_dir,
                "main_file": web_index,
                "requires_install": False,
                "install_command": [],
                "has_dev_server": False,
                "has_docs": False,
            }

        # 5. Generic Python Script
        py_files = [f for f in files if f.endswith(".py")]
        if py_files:
            main_py = "main.py" if "main.py" in py_files else "app.py" if "app.py" in py_files else py_files[0]
            return {
                "project_type": "Python Script",
                "runtime_type": "cli",
                "is_web": False,
                "port": None,
                "url": None,
                "command": [python_exe, str(ws_root / main_py)],
                "cwd": str(ws_root),
                "main_file": main_py,
                "requires_install": False,
                "install_command": [],
                "has_dev_server": False,
                "has_docs": False,
            }

        # 6. Rust project (Cargo.toml)
        if "Cargo.toml" in files or any(f.endswith("Cargo.toml") for f in files):
            return {
                "project_type": "Rust Application",
                "runtime_type": "cli",
                "is_web": False,
                "port": None,
                "url": None,
                "command": ["cargo", "run"],
                "cwd": str(ws_root),
                "main_file": "src/main.rs" if "src/main.rs" in files else "Cargo.toml",
                "requires_install": False,
                "install_command": ["cargo", "build"],
                "has_dev_server": False,
                "has_docs": False,
            }

        # 7. Go project (go.mod)
        if "go.mod" in files or any(f.endswith("go.mod") for f in files):
            return {
                "project_type": "Go Application",
                "runtime_type": "cli",
                "is_web": False,
                "port": None,
                "url": None,
                "command": ["go", "run", "."],
                "cwd": str(ws_root),
                "main_file": "main.go" if "main.go" in files else "go.mod",
                "requires_install": False,
                "install_command": ["go", "build"],
                "has_dev_server": False,
                "has_docs": False,
            }

        # Fallback default
        has_tests = any("test" in f.lower() for f in files)
        return {
            "project_type": "General Software Project",
            "runtime_type": "library" if has_tests else "cli",
            "is_web": False,
            "port": None,
            "url": None,
            "command": [],
            "cwd": str(ws_root),
            "main_file": files[0] if files else "",
            "requires_install": False,
            "install_command": [],
            "has_dev_server": False,
            "has_docs": False,
        }
