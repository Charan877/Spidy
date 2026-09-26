import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ProjectStateSnapshot } from '../types/state';

interface ComputationalMachineProps {
  state: ProjectStateSnapshot;
  scrollProgress: number; // 0.0 to 1.0 (continuous across 8 stages)
}

// 12 Modular Service Pod Configurations across 3 vertical tiers
interface PodConfig {
  id: number;
  tier: number;       // 0, 1, 2
  axisIndex: number;  // 0: +X, 1: +Z, 2: -X, 3: -Z
  angle: number;
  yPos: number;
  outerPos: THREE.Vector3;
  dockedPos: THREE.Vector3;
  ejectedPos: THREE.Vector3;
  label: string;
}

export const ComputationalMachine: React.FC<ComputationalMachineProps> = ({
  state,
  scrollProgress,
}) => {
  const machineRef = useRef<THREE.Group>(null);
  const spineRef = useRef<THREE.Group>(null);
  const wafersRef = useRef<THREE.Group>(null);
  const podsGroupRef = useRef<THREE.Group>(null);
  const scanBeamRef = useRef<THREE.Mesh>(null);
  const clampTopRef = useRef<THREE.Mesh>(null);
  const clampBottomRef = useRef<THREE.Mesh>(null);

  const phase = state.current_phase || 'DISCOVER';
  const progress = state.progress_percent || 0;
  const isBuilding =
    state.is_running ||
    ['PLAN', 'ARCHITECT', 'BUILD', 'RUN', 'TEST', 'DEBUG', 'REVIEW'].includes(phase);
  const isDebug = phase === 'DEBUG';
  const isComplete = phase === 'COMPLETE' || state.project_success;
  const isTesting = phase === 'TEST' || phase === 'REVIEW';

  // Generate 12 Modular Service Pod Coordinates
  const pods = useMemo<PodConfig[]>(() => {
    const list: PodConfig[] = [];
    const tierHeights = [-1.15, 0.0, 1.15];
    const rOuter = 3.65;
    const rDocked = 1.35;
    const rEjected = 2.65;
    const labels = [
      'ROUTER', 'DATA_LAYER', 'AUTH_GATEWAY', 'CACHE_BUS',
      'API_DISPATCH', 'RUNTIME_KERNEL', 'EVENT_BROKER', 'SCHEMA_VALIDATOR',
      'PROCESS_CONTROLLER', 'TELEMETRY_NODE', 'LOGIC_PIPELINE', 'HEALTH_PROBE',
    ];

    for (let tier = 0; tier < 3; tier++) {
      const y = tierHeights[tier];
      for (let a = 0; a < 4; a++) {
        const id = tier * 4 + a;
        const angle = a * (Math.PI / 2);
        const dirX = Math.cos(angle);
        const dirZ = Math.sin(angle);

        list.push({
          id,
          tier,
          axisIndex: a,
          angle,
          yPos: y,
          outerPos: new THREE.Vector3(dirX * rOuter, y, dirZ * rOuter),
          dockedPos: new THREE.Vector3(dirX * rDocked, y, dirZ * rDocked),
          ejectedPos: new THREE.Vector3(dirX * rEjected, y, dirZ * rEjected),
          label: labels[id] || `SERVICE_${id}`,
        });
      }
    }
    return list;
  }, []);

  // Shared calibrated materials for physical readability & high contrast
  const podMaterials = useMemo(() => {
    return {
      chassis: new THREE.MeshStandardMaterial({
        color: '#2a4164', // Distinct titanium graphite with clear diffuse body
        roughness: 0.35,
        metalness: 0.62,
        emissive: '#0d1d32',
        emissiveIntensity: 0.32,
      }),
      chassisBevel: new THREE.MeshStandardMaterial({
        color: '#60a5fa', // Brilliant chamfered edge highlight
        roughness: 0.16,
        metalness: 0.85,
        emissive: '#1e40af',
        emissiveIntensity: 0.45,
      }),
      recessedFace: new THREE.MeshStandardMaterial({
        color: '#16253c',
        roughness: 0.4,
        metalness: 0.65,
        emissive: '#081220',
        emissiveIntensity: 0.25,
      }),
      heatSink: new THREE.MeshStandardMaterial({
        color: '#3b557a', // Distinct horizontal fin stack
        roughness: 0.22,
        metalness: 0.82,
        emissive: '#10223a',
        emissiveIntensity: 0.25,
      }),
      titaniumBracket: new THREE.MeshStandardMaterial({
        color: '#223854',
        roughness: 0.22,
        metalness: 0.85,
        emissive: '#0c1b30',
        emissiveIntensity: 0.2,
      }),
      smokedGlass: new THREE.MeshStandardMaterial({
        color: '#1a365d',
        roughness: 0.08,
        metalness: 0.15,
        transparent: true,
        opacity: 0.38, // Clear visible internal depth
      }),
      pcbSubstrate: new THREE.MeshStandardMaterial({
        color: '#0e2038',
        roughness: 0.32,
        metalness: 0.6,
      }),
      icChip: new THREE.MeshStandardMaterial({
        color: '#0a172e',
        roughness: 0.2,
        metalness: 0.75,
        emissive: '#38bdf8',
        emissiveIntensity: 0.25,
      }),
      goldAccent: new THREE.MeshStandardMaterial({
        color: '#f59e0b', // Restrained gold accent
        roughness: 0.15,
        metalness: 0.95,
        emissive: '#78350f',
        emissiveIntensity: 0.3,
      }),
      fastener: new THREE.MeshStandardMaterial({
        color: '#475569',
        roughness: 0.18,
        metalness: 0.95,
      }),
      traceCyan: new THREE.MeshBasicMaterial({
        color: '#38bdf8',
        transparent: true,
        opacity: 0.95,
      }),
      traceSlate: new THREE.MeshBasicMaterial({
        color: '#94a3b8',
        transparent: true,
        opacity: 0.75,
      }),
      railGuideShoe: new THREE.MeshStandardMaterial({
        color: '#2a4164',
        roughness: 0.25,
        metalness: 0.85,
        emissive: '#11223b',
        emissiveIntensity: 0.3,
      }),
    };
  }, []);

  // Diagnostic Recovery Conduit Geometry
  const diagnosticGeo = useMemo(() => {
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(-1.2, 0.4, 0.8),
      new THREE.Vector3(-2.65, 0.0, 0.0) // Ejected pod #6 position
    );
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(31));
  }, []);

  const diagnosticConduitMesh = useMemo(() => {
    return new THREE.Line(
      diagnosticGeo,
      new THREE.LineBasicMaterial({
        color: new THREE.Color('#f59e0b'),
        transparent: true,
        opacity: 0.85,
      })
    );
  }, [diagnosticGeo]);

  // 6 Optical Prism Gates in Overhead Canopy
  const canopyPrisms = useMemo(() => {
    const list: { name: keyof typeof state.verification_gates; pos: [number, number, number] }[] = [
      { name: 'build', pos: [1.2, 2.35, 0] },
      { name: 'process', pos: [0.6, 2.35, 1.04] },
      { name: 'port', pos: [-0.6, 2.35, 1.04] },
      { name: 'server', pos: [-1.2, 2.35, 0] },
      { name: 'http', pos: [-0.6, 2.35, -1.04] },
      { name: 'application', pos: [0.6, 2.35, -1.04] },
    ];
    return list;
  }, []);

  useFrame((sceneState, delta) => {
    const t = sceneState.clock.getElapsedTime();
    const p = Math.max(0, Math.min(1, scrollProgress));

    // 1. Machine rotation & subtle floating drift
    if (machineRef.current) {
      const rotSpeed = isComplete ? 0.025 : isDebug ? 0.04 : isBuilding ? 0.12 : 0.06;
      machineRef.current.rotation.y += delta * rotSpeed;
      machineRef.current.position.y = Math.sin(t * 0.45) * 0.04;
    }

    // 2. Internal Micro-Wafer Logic stack breathing & computation pulses
    if (wafersRef.current) {
      wafersRef.current.children.forEach((wafer, i) => {
        const mesh = wafer as THREE.Mesh;
        const mat = mesh.material as THREE.MeshStandardMaterial;
        if (mat) {
          const wave = Math.sin(t * 3.2 - i * 0.7);
          const baseIntensity = isBuilding ? 0.48 : 0.22;
          mat.emissiveIntensity = baseIntensity + (wave > 0 ? wave * 0.38 : 0);
          mesh.scale.set(
            1.0 + (wave > 0.85 ? 0.012 : 0),
            1.0,
            1.0 + (wave > 0.85 ? 0.012 : 0)
          );
        }
      });
    }

    // 3. Planar Laser Scan Beam during TEST / REVIEW
    let currentScanY = 0;
    const showScanner = isTesting || (p >= 0.5 && p < 0.65);
    if (scanBeamRef.current) {
      scanBeamRef.current.visible = showScanner;
      if (showScanner) {
        currentScanY = Math.sin(t * 2.0) * 1.6;
        scanBeamRef.current.position.y = currentScanY;
        const scanMat = scanBeamRef.current.material as THREE.MeshBasicMaterial;
        if (scanMat) {
          scanMat.opacity = 0.35 + Math.sin(t * 5) * 0.15;
        }
      }
    }

    // 4. Precision Mechanical Pod Movement along Magnetic Rails
    if (podsGroupRef.current) {
      const dockedCount = isBuilding
        ? Math.floor((progress / 100) * 12)
        : Math.floor(p * 12);

      podsGroupRef.current.children.forEach((child, idx) => {
        const pod = pods[idx];
        if (!pod) return;

        let targetPos = pod.outerPos;
        const isFaultyPod = isDebug && pod.id === 6;

        if (isFaultyPod) {
          // Autonomous fault isolation: pod #6 ejects along -X rail
          targetPos = pod.ejectedPos;
        } else if (idx < dockedCount || isComplete) {
          // Precision docked position with micro vibration during active compile
          const microJitter = isBuilding ? (Math.random() - 0.5) * 0.003 : 0;
          targetPos = new THREE.Vector3(
            pod.dockedPos.x + microJitter,
            pod.dockedPos.y,
            pod.dockedPos.z + microJitter
          );
        } else {
          // Staged at outer rail positions with gentle mechanical idle breathing
          const idleDrift = Math.sin(t * 1.2 + pod.tier * 0.7) * 0.03;
          targetPos = new THREE.Vector3(
            pod.outerPos.x + Math.cos(pod.angle) * idleDrift,
            pod.outerPos.y,
            pod.outerPos.z + Math.sin(pod.angle) * idleDrift
          );
        }

        // Smooth physical damping
        child.position.lerp(targetPos, 0.08);

        // Check if planar laser scan beam is currently passing over this pod
        const isBeingScanned = showScanner && Math.abs(currentScanY - pod.yPos) < 0.32;

        // Active component illumination response
        const podMesh = child as THREE.Group;
        const mainMesh = podMesh.children[0] as THREE.Mesh;
        if (mainMesh && mainMesh.material) {
          const mat = mainMesh.material as THREE.MeshStandardMaterial;
          if (isFaultyPod) {
            mat.emissive.set('#f59e0b');
            mat.emissiveIntensity = 0.85 + Math.sin(t * 8) * 0.35;
          } else if (isBeingScanned) {
            mat.emissive.set('#38bdf8');
            mat.emissiveIntensity = 1.05;
          } else if (idx === dockedCount && isBuilding) {
            // Actively assembling pod receives prominent highlight
            mat.emissive.set('#38bdf8');
            mat.emissiveIntensity = 0.55 + Math.sin(t * 6) * 0.25;
          } else if (isComplete || idx < dockedCount) {
            const isVerified = isComplete || (isTesting && idx < dockedCount);
            mat.emissive.set(isVerified ? '#10b981' : '#38bdf8');
            mat.emissiveIntensity = isComplete ? 0.38 : isBuilding ? 0.35 : 0.18;
          } else {
            mat.emissive.set('#1e293b');
            mat.emissiveIntensity = 0.08;
          }
        }
      });
    }

    // 5. Diagnostic Recovery Conduit in DEBUG
    if (isDebug && diagnosticConduitMesh) {
      const lineMat = diagnosticConduitMesh.material as THREE.LineBasicMaterial;
      if (lineMat) {
        lineMat.opacity = 0.55 + Math.sin(t * 10) * 0.35;
      }
    }

    // 6. Complete Stabilized Hydraulic Clamps
    if (clampTopRef.current && clampBottomRef.current) {
      const targetTopY = isComplete ? 2.15 : 2.55;
      const targetBottomY = isComplete ? -2.15 : -2.55;
      clampTopRef.current.position.y += (targetTopY - clampTopRef.current.position.y) * 0.05;
      clampBottomRef.current.position.y += (targetBottomY - clampBottomRef.current.position.y) * 0.05;
    }
  });

  return (
    <group ref={machineRef} position={[0, 0, 0]}>
      {/* ================================================================= */}
      {/* 1. ROOT SUBSTRATE PLATFORM & MACHINED MAGNETIC GUIDE RAILS        */}
      {/* ================================================================= */}
      {/* Heavy Alloy Beveled Octagonal Base Deck */}
      <mesh position={[0, -2.62, 0]}>
        <cylinderGeometry args={[3.2, 3.55, 0.42, 8]} />
        <meshStandardMaterial
          color="#101928"
          roughness={0.32}
          metalness={0.88}
          envMapIntensity={0.85}
        />
      </mesh>

      {/* Recessed Substrate Deck Perimeter Channel Ring */}
      <mesh position={[0, -2.40, 0]}>
        <cylinderGeometry args={[2.82, 2.87, 0.06, 32]} />
        <meshStandardMaterial
          color="#1a2942"
          roughness={0.2}
          metalness={0.92}
          emissive="#1e3a5f"
          emissiveIntensity={0.2}
        />
      </mesh>

      {/* 4 Cardinal Linear Magnetic Guide Tracks with Dual Rails & Positional Datum */}
      {[0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2].map((angle, i) => (
        <group key={`rail-${i}`} rotation={[0, angle, 0]}>
          {/* Main heavy track bed */}
          <mesh position={[2.5, -2.36, 0]}>
            <boxGeometry args={[2.65, 0.06, 0.26]} />
            <meshStandardMaterial color="#142034" roughness={0.3} metalness={0.9} />
          </mesh>

          {/* Dual machined parallel steel guide rails with beveled edge */}
          <mesh position={[2.5, -2.31, 0.09]}>
            <boxGeometry args={[2.6, 0.035, 0.035]} />
            <meshStandardMaterial color="#283c5a" roughness={0.18} metalness={0.95} />
          </mesh>
          <mesh position={[2.5, -2.31, -0.09]}>
            <boxGeometry args={[2.6, 0.035, 0.035]} />
            <meshStandardMaterial color="#283c5a" roughness={0.18} metalness={0.95} />
          </mesh>

          {/* Central recessed magnetic stator trench */}
          <mesh position={[2.5, -2.33, 0]}>
            <boxGeometry args={[2.55, 0.015, 0.06]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.55} />
          </mesh>

          {/* Precision millimeter datum tick marks along rail */}
          {[1.4, 1.8, 2.2, 2.6, 3.0, 3.4, 3.7].map((rx, idx) => (
            <mesh key={`tick-${idx}`} position={[rx, -2.285, 0]}>
              <boxGeometry args={[0.015, 0.006, 0.18]} />
              <meshBasicMaterial color="#94a3b8" transparent opacity={0.5} />
            </mesh>
          ))}

          {/* Heavy mechanical end-stop buffer with restraint pins */}
          <mesh position={[3.82, -2.29, 0]}>
            <boxGeometry args={[0.06, 0.09, 0.28]} />
            <meshStandardMaterial color="#1e293b" roughness={0.3} metalness={0.9} />
          </mesh>
        </group>
      ))}

      {/* ================================================================= */}
      {/* 2. CENTRAL LOGIC COLUMN & SMOKED GLASS EXOSKELETON                */}
      {/* ================================================================= */}
      <group ref={spineRef} position={[0, 0, 0]}>
        {/* Four Heavy Titanium Corner Pylons with Chamfers and Embedded Optical Fibers */}
        {[
          [-0.8, -0.8],
          [0.8, -0.8],
          [0.8, 0.8],
          [-0.8, 0.8],
        ].map(([px, pz], idx) => (
          <group key={`pylon-grp-${idx}`}>
            {/* Main titanium structural pylon */}
            <mesh position={[px, 0, pz]}>
              <boxGeometry args={[0.16, 4.4, 0.16]} />
              <meshStandardMaterial
                color="#243c62"
                roughness={0.24}
                metalness={0.75}
                emissive="#0e1f38"
                emissiveIntensity={0.28}
              />
            </mesh>
            {/* Chamfered structural ridge catching specular highlights */}
            <mesh position={[px > 0 ? px - 0.02 : px + 0.02, 0, pz > 0 ? pz - 0.02 : pz + 0.02]}>
              <boxGeometry args={[0.04, 4.38, 0.04]} />
              <meshStandardMaterial
                color="#60a5fa"
                roughness={0.16}
                metalness={0.88}
                emissive="#1d4ed8"
                emissiveIntensity={0.5}
              />
            </mesh>
            {/* Embedded optical fiber line along corner */}
            <mesh position={[px > 0 ? px + 0.082 : px - 0.082, 0, pz]}>
              <cylinderGeometry args={[0.014, 0.014, 4.35, 8]} />
              <meshBasicMaterial color="#38bdf8" transparent opacity={0.85} />
            </mesh>
          </group>
        ))}

        {/* Smoked Glass Processing Chamber Exoskeleton Panels */}
        <mesh position={[0, 0, 0]}>
          <boxGeometry args={[1.52, 4.22, 1.52]} />
          <meshStandardMaterial
            color="#18355c"
            roughness={0.08}
            metalness={0.15}
            transparent
            opacity={0.34}
          />
        </mesh>

        {/* Internal Micro-Wafer Logic Stack (6 stacked silicon logic cassettes) */}
        <group ref={wafersRef}>
          {[-1.5, -0.9, -0.3, 0.3, 0.9, 1.5].map((wy, idx) => (
            <group key={`wafer-grp-${idx}`} position={[0, wy, 0]}>
              {/* Silicon Wafer Substrate Tray */}
              <mesh position={[0, 0, 0]}>
                <boxGeometry args={[1.22, 0.035, 1.22]} />
                <meshStandardMaterial
                  color="#1c3b68"
                  roughness={0.25}
                  metalness={0.75}
                  emissive="#38bdf8"
                  emissiveIntensity={0.55}
                />
              </mesh>
              {/* Edge retention clips at 4 corners */}
              {[[-0.58, -0.58], [0.58, -0.58], [0.58, 0.58], [-0.58, 0.58]].map(([cx, cz], cIdx) => (
                <mesh key={`clip-${cIdx}`} position={[cx, 0.015, cz]}>
                  <boxGeometry args={[0.04, 0.04, 0.04]} />
                  <meshStandardMaterial color="#28384f" roughness={0.2} metalness={0.95} />
                </mesh>
              ))}
            </group>
          ))}
        </group>

        {/* Vertical Optical Trunk Conduit along center */}
        <mesh position={[0, 0, 0]}>
          <cylinderGeometry args={[0.11, 0.11, 4.3, 16]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.42} />
        </mesh>
      </group>

      {/* ================================================================= */}
      {/* 3. 12 MODULAR SERVICE PODS (Engineered with Internal Depth)        */}
      {/* ================================================================= */}
      <group ref={podsGroupRef}>
        {pods.map((pod) => (
          <group
            key={`pod-${pod.id}`}
            position={pod.outerPos}
            rotation={[0, -pod.angle + Math.PI / 2, 0]}
          >
            {/* 1. Main Beveled Outer Chassis Frame */}
            <mesh position={[0, 0, 0]} material={podMaterials.chassis}>
              <boxGeometry args={[0.78, 0.48, 0.40]} />
            </mesh>

            {/* 2. Beveled Top & Bottom Edge Accent Chamfers */}
            <mesh position={[0, 0.236, 0]} material={podMaterials.chassisBevel}>
              <boxGeometry args={[0.76, 0.012, 0.38]} />
            </mesh>
            <mesh position={[0, -0.236, 0]} material={podMaterials.chassisBevel}>
              <boxGeometry args={[0.76, 0.012, 0.38]} />
            </mesh>

            {/* 3. Recessed Stepped Faceplate Frame */}
            <mesh position={[0, 0, 0.19]} material={podMaterials.recessedFace}>
              <boxGeometry args={[0.68, 0.38, 0.025]} />
            </mesh>

            {/* 4. Layered Horizontal Heat-Sink Cooling Fins on Top Deck */}
            <group position={[0, 0.245, 0]}>
              {[-0.09, -0.03, 0.03, 0.09].map((fz, idx) => (
                <mesh key={`fin-${idx}`} position={[0, 0.015, fz]} material={podMaterials.heatSink}>
                  <boxGeometry args={[0.68, 0.018, 0.022]} />
                </mesh>
              ))}
            </group>

            {/* 5. Titanium Structural Side Reinforcement Brackets */}
            <mesh position={[-0.388, 0, 0]} material={podMaterials.titaniumBracket}>
              <boxGeometry args={[0.026, 0.44, 0.36]} />
            </mesh>
            <mesh position={[0.388, 0, 0]} material={podMaterials.titaniumBracket}>
              <boxGeometry args={[0.026, 0.44, 0.36]} />
            </mesh>

            {/* 6. Precision Fasteners: 4 Corner Hex Bolt Caps on Face */}
            {[
              [-0.31, 0.16],
              [0.31, 0.16],
              [-0.31, -0.16],
              [0.31, -0.16],
            ].map(([bx, by], idx) => (
              <mesh key={`bolt-${idx}`} position={[bx, by, 0.204]} material={podMaterials.fastener} rotation={[Math.PI / 2, 0, 0]}>
                <cylinderGeometry args={[0.011, 0.011, 0.008, 6]} />
              </mesh>
            ))}

            {/* 7. Smoked Glass Inspection Window */}
            <mesh position={[0, 0, 0.205]} material={podMaterials.smokedGlass}>
              <planeGeometry args={[0.60, 0.30]} />
            </mesh>

            {/* 8. Multi-Layer Internal Cavity behind Glass (Deep Engineering Depth) */}
            <group position={[0, 0, 0.165]}>
              {/* Internal PCB Substrate */}
              <mesh position={[0, 0, 0]} material={podMaterials.pcbSubstrate}>
                <planeGeometry args={[0.58, 0.28]} />
              </mesh>

              {/* Surface-Mount Central Microprocessor QFP IC */}
              <mesh position={[0, 0, 0.012]} material={podMaterials.icChip}>
                <boxGeometry args={[0.13, 0.13, 0.018]} />
              </mesh>
              {/* IC corner gold grounding pad */}
              <mesh position={[0.05, 0.05, 0.022]} material={podMaterials.goldAccent}>
                <boxGeometry args={[0.018, 0.018, 0.004]} />
              </mesh>

              {/* Twin Auxiliary Memory ICs */}
              <mesh position={[-0.18, 0.02, 0.01]} material={podMaterials.icChip}>
                <boxGeometry args={[0.08, 0.05, 0.014]} />
              </mesh>
              <mesh position={[0.18, 0.02, 0.01]} material={podMaterials.icChip}>
                <boxGeometry args={[0.08, 0.05, 0.014]} />
              </mesh>

              {/* 3D Etched Micro-Circuit Traces */}
              <mesh position={[0, 0.07, 0.004]} material={podMaterials.traceCyan}>
                <planeGeometry args={[0.52, 0.012]} />
              </mesh>
              <mesh position={[0, -0.06, 0.004]} material={podMaterials.traceSlate}>
                <planeGeometry args={[0.48, 0.012]} />
              </mesh>
              <mesh position={[-0.12, 0, 0.004]} material={podMaterials.traceCyan}>
                <planeGeometry args={[0.012, 0.16]} />
              </mesh>
              <mesh position={[0.12, 0, 0.004]} material={podMaterials.traceCyan}>
                <planeGeometry args={[0.012, 0.16]} />
              </mesh>
            </group>

            {/* 9. Front Trio of Micro-LED Status Diodes (Clock, Bus, Gate) */}
            {[-0.22, -0.16, -0.10].map((lx, idx) => (
              <mesh key={`mled-${idx}`} position={[lx, 0.14, 0.207]}>
                <sphereGeometry args={[0.012, 8, 8]} />
                <meshBasicMaterial
                  color={idx === 2 && isDebug && pod.id === 6 ? '#f59e0b' : idx === 0 ? '#10b981' : '#38bdf8'}
                  transparent
                  opacity={0.85}
                />
              </mesh>
            ))}

            {/* 10. Bottom Magnetic Rail Slider Carriage & Guide Shoes */}
            <mesh position={[0, -0.245, 0]} material={podMaterials.railGuideShoe}>
              <boxGeometry args={[0.26, 0.032, 0.22]} />
            </mesh>
            {/* Restrained gold contact brush on bottom */}
            <mesh position={[0, -0.262, 0]} material={podMaterials.goldAccent}>
              <boxGeometry args={[0.08, 0.006, 0.12]} />
            </mesh>

            {/* 11. Rear Mechanical Docking Coupling with Dual Alignment Pins */}
            <mesh position={[0, 0, -0.21]} material={podMaterials.chassisBevel}>
              <boxGeometry args={[0.32, 0.32, 0.035]} />
            </mesh>
            <mesh position={[-0.10, 0, -0.235]} material={podMaterials.fastener} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.012, 0.015, 0.03, 8]} />
            </mesh>
            <mesh position={[0.10, 0, -0.235]} material={podMaterials.fastener} rotation={[Math.PI / 2, 0, 0]}>
              <cylinderGeometry args={[0.012, 0.015, 0.03, 8]} />
            </mesh>
            {/* Gold connector pins in rear socket */}
            <mesh position={[0, 0, -0.228]} material={podMaterials.goldAccent}>
              <boxGeometry args={[0.06, 0.03, 0.005]} />
            </mesh>
          </group>
        ))}
      </group>

      {/* ================================================================= */}
      {/* 4. PLANAR LASER SCANNER (Sweeps during TEST & REVIEW)             */}
      {/* ================================================================= */}
      <mesh ref={scanBeamRef} position={[0, 0, 0]} rotation={[Math.PI / 2, 0, 0]} visible={false}>
        <ringGeometry args={[0.85, 3.85, 32]} />
        <meshBasicMaterial
          color="#38bdf8"
          transparent
          opacity={0.3}
          side={THREE.DoubleSide}
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </mesh>

      {/* ================================================================= */}
      {/* 5. DIAGNOSTIC RECOVERY CONDUIT (Active in DEBUG/RECOVER)          */}
      {/* ================================================================= */}
      <primitive object={diagnosticConduitMesh} visible={isDebug} />

      {/* ================================================================= */}
      {/* 6. OVERHEAD VERIFICATION CANOPY & 6 OPTICAL PRISMS                */}
      {/* ================================================================= */}
      <group position={[0, 0, 0]}>
        {/* Hexagonal Top Structural Crown with Beveled Profile & Glowing Edge */}
        <mesh position={[0, 2.3, 0]}>
          <cylinderGeometry args={[2.05, 1.68, 0.26, 6]} />
          <meshStandardMaterial
            color="#2a456c"
            roughness={0.22}
            metalness={0.75}
            emissive="#122544"
            emissiveIntensity={0.35}
          />
        </mesh>
        {/* Glowing Crown Accent Rim */}
        <mesh position={[0, 2.44, 0]}>
          <cylinderGeometry args={[2.07, 2.05, 0.035, 6]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.75} />
        </mesh>

        {/* 6 Optical Verification Gate Prisms */}
        {canopyPrisms.map((prism) => {
          const isGatePassed = state.verification_gates?.[prism.name];
          return (
            <mesh key={`prism-${prism.name}`} position={prism.pos}>
              <octahedronGeometry args={[0.13, 0]} />
              <meshStandardMaterial
                color={isGatePassed ? '#10b981' : '#254a78'}
                emissive={isGatePassed ? '#10b981' : '#38bdf8'}
                emissiveIntensity={isGatePassed ? 1.4 : 0.6}
                roughness={0.12}
                metalness={0.9}
              />
            </mesh>
          );
        })}
      </group>

      {/* ================================================================= */}
      {/* 7. HYDRAULIC STRUCTURAL CLAMPS (Seal in COMPLETE)                 */}
      {/* ================================================================= */}
      <mesh ref={clampTopRef} position={[0, 2.58, 0]}>
        <cylinderGeometry args={[1.72, 1.82, 0.16, 8]} />
        <meshStandardMaterial
          color="#253e62"
          roughness={0.2}
          metalness={0.82}
          emissive="#0e2038"
          emissiveIntensity={0.3}
        />
      </mesh>
      <mesh ref={clampBottomRef} position={[0, -2.58, 0]}>
        <cylinderGeometry args={[1.82, 1.72, 0.16, 8]} />
        <meshStandardMaterial
          color="#253e62"
          roughness={0.2}
          metalness={0.82}
          emissive="#0e2038"
          emissiveIntensity={0.3}
        />
      </mesh>
    </group>
  );
};
