"""Three.js 3D Computational World and Agent Constellation for SPIDY.

Renders an immersive, real-time WebGL 3D environment:
- Procedural crystalline computational core (nested icosahedron/dodecahedron lattice)
- Spatial 3D agent network (Planner, Architect, Developer, Debugger, Tester, Reviewer)
- 3D energy bezier conduits with animated data pulses
- Concentric orbital data rings
- Volumetric starfield & floating syntax particles
- Cinematic PerspectiveCamera with mouse parallax tracking
- Progressive fallback to high-fidelity Canvas 2D procedural rendering if WebGL is unavailable
"""

import json


def get_state_canvas_html(state_mode: str = "IDLE", height: int = 560, active_agent: str = "") -> str:
    """Returns a full-featured Three.js WebGL 3D computational world HTML string."""
    mode = (state_mode or "IDLE").upper()
    if mode not in ("IDLE", "PLANNING", "BUILDING", "DEBUGGING", "VERIFYING", "SUCCESS"):
        if "BUILD" in mode or "GEN" in mode:
            mode = "BUILDING"
        elif "PLAN" in mode or "ARCH" in mode:
            mode = "PLANNING"
        elif "DEBUG" in mode:
            mode = "DEBUGGING"
        elif "VERIF" in mode or "TEST" in mode or "RUN" in mode:
            mode = "VERIFYING"
        elif "SUCC" in mode or "COMPL" in mode:
            mode = "SUCCESS"
        else:
            mode = "IDLE"

    agent_str = active_agent or (
        "Developer" if mode == "BUILDING" else
        "Planner" if mode == "PLANNING" else
        "Debugger" if mode == "DEBUGGING" else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html, body {{
    width: 100%;
    height: 100%;
    overflow: hidden;
    background: radial-gradient(circle at 55% 45%, rgba(15, 23, 42, 0.7) 0%, rgba(4, 7, 17, 0.98) 80%);
    font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
  }}
  #container {{
    position: relative;
    width: 100%;
    height: 100%;
    min-height: {height}px;
  }}
  #canvas3d {{
    width: 100%;
    height: 100%;
    display: block;
  }}
  .agent-tag {{
    position: absolute;
    pointer-events: none;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #94a3b8;
    background: rgba(8, 12, 24, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.14);
    padding: 3px 8px;
    border-radius: 4px;
    transform: translate(-50%, -50%);
    white-space: nowrap;
    transition: color 0.3s, border-color 0.3s, box-shadow 0.3s;
    user-select: none;
  }}
  .agent-tag.active {{
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.75);
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.45);
    background: rgba(14, 28, 54, 0.92);
  }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
  if (typeof THREE === 'undefined') {{
    document.write('<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"><\\/script>');
  }}
</script>
</head>
<body>
<div id="container">
  <canvas id="canvas3d"></canvas>
  <div id="tags"></div>
</div>
<script>
(function() {{
  const currentMode = {json.dumps(mode)};
  const activeAgentName = {json.dumps(agent_str)};
  const container = document.getElementById('container');
  const canvas = document.getElementById('canvas3d');
  const tagsContainer = document.getElementById('tags');

  function hasWebGL() {{
    try {{
      const c = document.createElement('canvas');
      return !!(window.WebGLRenderingContext && (c.getContext('webgl') || c.getContext('experimental-webgl')));
    }} catch (e) {{
      return false;
    }}
  }}

  if (typeof THREE === 'undefined' || !hasWebGL()) {{
    startCanvas2DFallback();
    return;
  }}

  startThreeWebGL();

  function startThreeWebGL() {{
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x040711, 0.035);

    const getW = () => container.clientWidth || window.innerWidth || 640;
    const getH = () => container.clientHeight || window.innerHeight || {height};

    const camera = new THREE.PerspectiveCamera(45, getW() / getH(), 0.1, 100);
    camera.position.set(0, 0.9, 9.2);

    let renderer;
    try {{
      renderer = new THREE.WebGLRenderer({{ canvas: canvas, antialias: true, alpha: true }});
      renderer.setSize(getW(), getH());
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    }} catch (err) {{
      startCanvas2DFallback();
      return;
    }}

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const lightCyan = new THREE.PointLight(0x38bdf8, 2.6, 25);
    lightCyan.position.set(5, 5, 5);
    scene.add(lightCyan);

    const lightViolet = new THREE.PointLight(0x818cf8, 2.2, 25);
    lightViolet.position.set(-5, -4, 4);
    scene.add(lightViolet);

    const lightRose = new THREE.PointLight(0xf43f5e, 1.8, 25);
    lightRose.position.set(0, -6, 2);
    scene.add(lightRose);

    // Phase color config
    const PALETTES = {{
      IDLE:      {{ primary: 0x6366f1, core: 0x38bdf8, glow: 0x818cf8, rotSpeed: 0.005 }},
      PLANNING:  {{ primary: 0x38bdf8, core: 0x06b6d4, glow: 0x38bdf8, rotSpeed: 0.008 }},
      BUILDING:  {{ primary: 0xa855f7, core: 0x818cf8, glow: 0xc084fc, rotSpeed: 0.015 }},
      DEBUGGING: {{ primary: 0xf43f5e, core: 0xfbbf24, glow: 0xf43f5e, rotSpeed: 0.022 }},
      VERIFYING: {{ primary: 0x10b981, core: 0x34d399, glow: 0x10b981, rotSpeed: 0.007 }},
      SUCCESS:   {{ primary: 0x34d399, core: 0x10b981, glow: 0x34d399, rotSpeed: 0.004 }}
    }};
    const conf = PALETTES[currentMode] || PALETTES.IDLE;

    // 1. Central Computational Core
    const coreGroup = new THREE.Group();
    scene.add(coreGroup);

    const outerGeo = new THREE.IcosahedronGeometry(2.1, 1);
    const outerMat = new THREE.MeshStandardMaterial({{
      color: conf.primary,
      emissive: conf.primary,
      emissiveIntensity: 0.28,
      roughness: 0.25,
      metalness: 0.75,
      transparent: true,
      opacity: 0.82,
      wireframe: currentMode === 'PLANNING'
    }});
    const outerMesh = new THREE.Mesh(outerGeo, outerMat);
    coreGroup.add(outerMesh);

    const innerGeo = new THREE.DodecahedronGeometry(1.15, 0);
    const innerMat = new THREE.MeshStandardMaterial({{
      color: conf.core,
      emissive: conf.core,
      emissiveIntensity: 0.9,
      roughness: 0.1,
      metalness: 0.9
    }});
    const innerMesh = new THREE.Mesh(innerGeo, innerMat);
    coreGroup.add(innerMesh);

    const wireMat = new THREE.LineBasicMaterial({{ color: conf.glow, transparent: true, opacity: 0.45 }});
    const wireGeo = new THREE.WireframeGeometry(new THREE.IcosahedronGeometry(2.25, 1));
    const wireMesh = new THREE.LineSegments(wireGeo, wireMat);
    coreGroup.add(wireMesh);

    // Orbital Rings
    const ring1 = new THREE.Mesh(
      new THREE.TorusGeometry(3.2, 0.025, 16, 100),
      new THREE.MeshBasicMaterial({{ color: 0x818cf8, transparent: true, opacity: 0.42 }})
    );
    ring1.rotation.x = Math.PI / 3;
    coreGroup.add(ring1);

    const ring2 = new THREE.Mesh(
      new THREE.TorusGeometry(3.8, 0.02, 16, 100),
      new THREE.MeshBasicMaterial({{ color: 0x38bdf8, transparent: true, opacity: 0.3 }})
    );
    ring2.rotation.y = Math.PI / 4;
    ring2.rotation.x = Math.PI / 6;
    coreGroup.add(ring2);

    // 2. Spatial Agent Network
    const AGENTS = [
      {{ id: 'planner',   name: 'Planner',   pos: [0, 3.2, 0.3],    color: 0x38bdf8 }},
      {{ id: 'architect', name: 'Architect', pos: [-3.4, 1.5, -0.4], color: 0x818cf8 }},
      {{ id: 'developer', name: 'Developer', pos: [3.4, 1.4, 0.3],  color: 0xa855f7 }},
      {{ id: 'debugger',  name: 'Debugger',  pos: [-2.7, -2.0, 0.4],color: 0xf43f5e }},
      {{ id: 'tester',    name: 'Tester',    pos: [2.7, -2.0, -0.3],color: 0x10b981 }},
      {{ id: 'reviewer',  name: 'Reviewer',  pos: [0, -3.2, 0.2],   color: 0x34d399 }},
    ];

    const agentNodes = [];
    const tagElements = [];

    AGENTS.forEach((agent) => {{
      const nodeGroup = new THREE.Group();
      nodeGroup.position.set(...agent.pos);

      const isActive = activeAgentName.toLowerCase().includes(agent.id) ||
        (currentMode === 'BUILDING' && agent.id === 'developer') ||
        (currentMode === 'DEBUGGING' && agent.id === 'debugger') ||
        (currentMode === 'PLANNING' && agent.id === 'planner');

      const sphere = new THREE.Mesh(
        new THREE.SphereGeometry(isActive ? 0.36 : 0.25, 24, 24),
        new THREE.MeshStandardMaterial({{
          color: agent.color,
          emissive: agent.color,
          emissiveIntensity: isActive ? 1.8 : 0.45,
          roughness: 0.2,
          metalness: 0.8
        }})
      );
      nodeGroup.add(sphere);

      const halo = new THREE.Mesh(
        new THREE.RingGeometry(0.40, 0.46, 32),
        new THREE.MeshBasicMaterial({{
          color: agent.color,
          transparent: true,
          opacity: isActive ? 0.9 : 0.22,
          side: THREE.DoubleSide
        }})
      );
      nodeGroup.add(halo);
      scene.add(nodeGroup);

      // Conduit to core
      const curve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(...agent.pos),
        new THREE.Vector3(agent.pos[0] * 0.5, agent.pos[1] * 0.5, 0.7),
        new THREE.Vector3(0, 0, 0)
      );
      const conduitGeo = new THREE.BufferGeometry().setFromPoints(curve.getPoints(24));
      const conduitMat = new THREE.LineBasicMaterial({{
        color: agent.color,
        transparent: true,
        opacity: isActive ? 0.8 : 0.18,
        linewidth: isActive ? 2 : 1
      }});
      const conduit = new THREE.Line(conduitGeo, conduitMat);
      scene.add(conduit);

      agentNodes.push({{ group: nodeGroup, halo: halo, sphere: sphere, data: agent, isActive: isActive }});

      // DOM Tag
      const tag = document.createElement('div');
      tag.className = 'agent-tag' + (isActive ? ' active' : '');
      tag.innerText = agent.name;
      tagsContainer.appendChild(tag);
      tagElements.push({{ el: tag, pos: new THREE.Vector3(...agent.pos) }});
    }});

    // 3. Particle Starfield
    const particleCount = 220;
    const pGeo = new THREE.BufferGeometry();
    const pPos = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount * 3; i += 3) {{
      const r = 2.0 + Math.random() * 5.0;
      const theta = Math.random() * Math.PI * 2;
      const phi = (Math.random() - 0.5) * Math.PI;
      pPos[i] = r * Math.cos(phi) * Math.cos(theta);
      pPos[i + 1] = r * Math.sin(phi);
      pPos[i + 2] = r * Math.cos(phi) * Math.sin(theta);
    }}
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
    const pMat = new THREE.PointsMaterial({{
      color: conf.glow,
      size: 0.055,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending
    }});
    const particleSystem = new THREE.Points(pGeo, pMat);
    scene.add(particleSystem);

    // Mouse Parallax
    let mouseX = 0, mouseY = 0, targetX = 0, targetY = 0;
    const onMouseMove = (e) => {{
      const w = window.innerWidth || 1;
      const h = window.innerHeight || 1;
      targetX = (e.clientX / w - 0.5) * 1.8;
      targetY = (e.clientY / h - 0.5) * 1.2;
    }};
    window.addEventListener('mousemove', onMouseMove, {{ passive: true }});
    try {{
      if (window.parent && window.parent !== window) {{
        window.parent.addEventListener('mousemove', onMouseMove, {{ passive: true }});
      }}
    }} catch (e) {{}}

    // Animation Loop
    let clock = new THREE.Clock();
    let animId;
    function animate() {{
      animId = requestAnimationFrame(animate);
      const delta = clock.getDelta();
      const t = clock.getElapsedTime();

      mouseX += (targetX - mouseX) * 0.05;
      mouseY += (targetY - mouseY) * 0.05;

      camera.position.x = mouseX * 1.2;
      camera.position.y = 0.9 - mouseY * 0.8;
      camera.lookAt(0, 0, 0);

      coreGroup.rotation.y += delta * conf.rotSpeed * 15;
      coreGroup.rotation.x = Math.sin(t * 0.5) * 0.12;

      wireMesh.rotation.y -= delta * 0.2;
      innerMesh.rotation.y += delta * 0.4;
      ring1.rotation.z += delta * 0.12;
      ring2.rotation.z -= delta * 0.08;

      const s = 1 + (currentMode === 'BUILDING' ? Math.sin(t * 4) * 0.06 : Math.sin(t * 1.5) * 0.03);
      outerMesh.scale.set(s, s, s);

      agentNodes.forEach((node) => {{
        node.halo.rotation.z += delta * (node.isActive ? 2.2 : 0.4);
      }});
      particleSystem.rotation.y += delta * 0.04;

      // Update screen space tags
      const curW = getW();
      const curH = getH();
      const hw = curW / 2;
      const hh = curH / 2;

      tagElements.forEach((item) => {{
        const wp = item.pos.clone().project(camera);
        const sx = wp.x * hw + hw;
        const sy = -wp.y * hh + hh + 26;
        item.el.style.left = sx + 'px';
        item.el.style.top = sy + 'px';
      }});

      renderer.render(scene, camera);
    }}
    animate();

    function onResize() {{
      const w = getW();
      const h = getH();
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    }}
    window.addEventListener('resize', onResize);
    setTimeout(onResize, 50);
    setTimeout(onResize, 250);
  }}

  // Canvas 2D Progressive Fallback
  function startCanvas2DFallback() {{
    const ctx = canvas.getContext('2d');
    let angle = 0;

    function render2D() {{
      const w = container.clientWidth || window.innerWidth || 640;
      const h = container.clientHeight || window.innerHeight || {height};
      canvas.width = w;
      canvas.height = h;

      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = '#040711';
      ctx.fillRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2;

      // Glow behind core
      const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, 180);
      grad.addColorStop(0, 'rgba(99, 102, 241, 0.25)');
      grad.addColorStop(1, 'rgba(4, 7, 17, 0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, 180, 0, Math.PI * 2);
      ctx.fill();

      // Rotating core wireframe
      angle += 0.015;
      ctx.strokeStyle = '#818cf8';
      ctx.lineWidth = 1.5;

      for (let ring = 0; ring < 3; ring++) {{
        ctx.beginPath();
        const rx = 70 + ring * 35;
        const ry = (70 + ring * 35) * Math.sin(angle * 0.7 + ring);
        ctx.ellipse(cx, cy, rx, Math.abs(ry) + 10, angle + ring * 0.8, 0, Math.PI * 2);
        ctx.stroke();
      }}

      // Agents in orbit
      const agentNames = ['Planner', 'Architect', 'Developer', 'Debugger', 'Tester', 'Reviewer'];
      const colors = ['#38bdf8', '#818cf8', '#a855f7', '#f43f5e', '#10b981', '#34d399'];

      agentNames.forEach((name, i) => {{
        const theta = angle * 0.4 + (i * Math.PI * 2) / 6;
        const ax = cx + Math.cos(theta) * 140;
        const ay = cy + Math.sin(theta) * 90;

        // Line to center
        ctx.strokeStyle = colors[i] + '44';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(ax, ay);
        ctx.stroke();

        // Node
        ctx.fillStyle = colors[i];
        ctx.beginPath();
        ctx.arc(ax, ay, 6, 0, Math.PI * 2);
        ctx.fill();

        // Label
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(name, ax, ay + 18);
      }});

      requestAnimationFrame(render2D);
    }}
    render2D();
  }}
}})();
</script>
</body>
</html>"""
