import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { ComputationalMachine } from './ComputationalMachine';
import { AgentConstellation } from './AgentConstellation';
import { DataStreams } from './DataStreams';
import { CinematicCamera } from './CinematicCamera';
import { FallbackCanvas } from './FallbackCanvas';
import { ProjectStateSnapshot } from '../types/state';

interface World3DProps {
  state: ProjectStateSnapshot;
  scrollProgress: number;
  onSelectAgent?: (id: string) => void;
}

// =====================================================================
// 1. MONUMENTAL ARCHITECTURAL BACKGROUND (z = -35 to -120)
// Features: Massive Quantum Halo Ring, Hyperbolic Structural Arches,
// Multi-Tiered Faceted Towers, Suspended Data Catwalks & Server Bays
// =====================================================================
const MonumentalBackground: React.FC<{ isBuilding: boolean }> = ({ isBuilding }) => {
  const groupRef = useRef<THREE.Group>(null);
  const haloRef = useRef<THREE.Group>(null);
  const dustRef = useRef<THREE.Points>(null);

  // 1. Enormous Overhead Arch Ribs (curving from floor to ceiling on left & right)
  const arches = useMemo(() => {
    const list: { pos: [number, number, number]; rot: [number, number, number]; scale: [number, number, number] }[] = [];
    const xPositions = [-24, 24];
    const zPositions = [-18, -32, -48, -64];

    xPositions.forEach((x) => {
      zPositions.forEach((z) => {
        // Vertical arch support pylon
        list.push({
          pos: [x, 7.5, z],
          rot: [0, 0, x > 0 ? -0.08 : 0.08],
          scale: [0.9, 25, 1.2],
        });
        // Cantilevered cross-truss rib angled inward
        list.push({
          pos: [x > 0 ? x - 4.5 : x + 4.5, 18.5, z],
          rot: [0, 0, x > 0 ? -0.42 : 0.42],
          scale: [10.5, 0.45, 0.9],
        });
      });
    });
    return list;
  }, []);

  // 2. Faceted Multi-Tiered Computational Towers
  const towers = useMemo(() => {
    const list: {
      pos: [number, number, number];
      scale: [number, number, number];
      color: string;
      metalness: number;
      roughness: number;
    }[] = [];

    // Mid-Far Tier (z = -38 to -52): High detail, distinct titanium graphite
    const tier1X = [-34, -18, 18, 34];
    tier1X.forEach((x, i) => {
      const z = -44 - (i % 2) * 6;
      const height = 55 + (i % 3) * 12;
      // Main column
      list.push({
        pos: [x, height / 2 - 18, z],
        scale: [3.2, height, 3.2],
        color: '#162844',
        metalness: 0.65,
        roughness: 0.32,
      });
      // Tier crown cap
      list.push({
        pos: [x, height - 17.5, z],
        scale: [4.0, 1.2, 4.0],
        color: '#223c62',
        metalness: 0.85,
        roughness: 0.22,
      });
      // Vertical recessed cooling channel
      list.push({
        pos: [x > 0 ? x - 1.55 : x + 1.55, height / 2 - 18, z],
        scale: [0.35, height - 4, 1.8],
        color: '#0c182c',
        metalness: 0.75,
        roughness: 0.45,
      });
    });

    // Far Tier (z = -65 to -85): Monumental scale
    const tier2X = [-44, -26, 0, 26, 44];
    tier2X.forEach((x, i) => {
      const z = -74 - (i % 3) * 6;
      const height = 80 + (i % 4) * 15;
      list.push({
        pos: [x, height / 2 - 25, z],
        scale: [5.2, height, 5.2],
        color: '#101f35',
        metalness: 0.72,
        roughness: 0.38,
      });
    });

    // Horizon Spires (z = -105 to -135): Atmospheric silhouettes
    const tier3X = [-55, -35, -15, 15, 35, 55];
    tier3X.forEach((x, i) => {
      const z = -115 - (i % 2) * 12;
      const height = 110 + (i % 3) * 25;
      list.push({
        pos: [x, height / 2 - 35, z],
        scale: [7.5, height, 7.5],
        color: '#0c182b',
        metalness: 0.8,
        roughness: 0.4,
      });
    });

    return list;
  }, []);

  // 3. Elevated High-Altitude Data Catwalks & Skybridges
  const bridges = useMemo(() => {
    const list: { pos: [number, number, number]; scale: [number, number, number] }[] = [];
    // Upper level skybridges
    list.push({ pos: [0, 16.5, -45], scale: [75, 0.45, 1.4] });
    list.push({ pos: [0, 6.5, -45], scale: [75, 0.35, 1.2] });
    list.push({ pos: [0, -3.5, -45], scale: [75, 0.35, 1.2] });
    // Diagonal cross-braces
    list.push({ pos: [-18, 11.5, -44.8], scale: [0.25, 11, 0.25] });
    list.push({ pos: [18, 11.5, -44.8], scale: [0.25, 11, 0.25] });
    return list;
  }, []);

  // 4. Practical Micro-Indicators & Server Rack Light Slits
  const serverLights = useMemo(() => {
    const list: { pos: [number, number, number]; color: string }[] = [];
    const towerX = [-34, -18, 18, 34];
    towerX.forEach((x) => {
      const z = -43.8;
      for (let y = -8; y <= 24; y += 2.2) {
        list.push({
          pos: [x > 0 ? x - 1.58 : x + 1.58, y, z],
          color: y % 4 === 0 ? '#38bdf8' : y % 3 === 0 ? '#6366f1' : '#0284c7',
        });
      }
    });
    return list;
  }, []);

  // 5. 280 Drifting Atmospheric Energy Particles across full depth
  const dustPositions = useMemo(() => {
    const count = 280;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 85;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 55;
      pos[i * 3 + 2] = -15 - Math.random() * 75;
    }
    return pos;
  }, []);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.05) * 0.12 + state.pointer.y * -0.15;
      groupRef.current.position.x = state.pointer.x * -0.22;
    }
    // Gentle rotation of the monumental Quantum Halo Ring
    if (haloRef.current) {
      haloRef.current.rotation.z = t * 0.02;
    }
    if (dustRef.current) {
      dustRef.current.rotation.y = t * 0.003;
    }
  });

  return (
    <>
      {/* 280 Floating Atmospheric Particles */}
      <points ref={dustRef} key="spidy-monumental-dust">
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={280}
            array={dustPositions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.042}
          color="#38bdf8"
          transparent
          opacity={0.38}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>

      <group ref={groupRef}>
        {/* ============================================================== */}
        {/* MONUMENTAL QUANTUM HALO RING (Framing the computational world) */}
        {/* ============================================================== */}
        <group ref={haloRef} position={[0, 4.0, -46]} rotation={[0.12, 0, 0]}>
          {/* Main Outer Accelerator Ring */}
          <mesh>
            <torusGeometry args={[23.5, 0.45, 16, 80]} />
            <meshStandardMaterial
              color="#223a5e"
              emissive="#1d4ed8"
              emissiveIntensity={0.25}
              roughness={0.25}
              metalness={0.88}
            />
          </mesh>

          {/* Glowing Inner Accelerator Track */}
          <mesh>
            <torusGeometry args={[22.6, 0.08, 12, 80]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.65} />
          </mesh>

          {/* Secondary Concentric Framing Ring */}
          <mesh>
            <torusGeometry args={[18.5, 0.18, 12, 64]} />
            <meshStandardMaterial
              color="#1a2e4c"
              emissive="#38bdf8"
              emissiveIntensity={0.18}
              roughness={0.3}
              metalness={0.9}
            />
          </mesh>

          {/* Cardinal Radial Spoke Braces */}
          {[0, Math.PI / 4, Math.PI / 2, (3 * Math.PI) / 4].map((rad, i) => (
            <mesh key={`halo-spoke-${i}`} rotation={[0, 0, rad]}>
              <boxGeometry args={[47, 0.18, 0.35]} />
              <meshStandardMaterial color="#1a2b44" roughness={0.3} metalness={0.92} />
            </mesh>
          ))}
        </group>

        {/* ============================================================== */}
        {/* OVERHEAD ARCHITECTURAL CATENARY RIBS & PYLONS                   */}
        {/* ============================================================== */}
        {arches.map((arch, idx) => (
          <mesh key={`arch-${idx}`} position={arch.pos} rotation={arch.rot} scale={arch.scale}>
            <boxGeometry />
            <meshStandardMaterial
              color="#1e3250"
              roughness={0.25}
              metalness={0.85}
              emissive="#0c1d35"
              emissiveIntensity={0.2}
            />
          </mesh>
        ))}

        {/* Embedded Linear Cyan Light Strips on Arches */}
        {[-23.8, 23.8].map((x, i) => (
          <mesh key={`arch-light-${i}`} position={[x, 7.5, -32]}>
            <boxGeometry args={[0.04, 24.5, 0.04]} />
            <meshBasicMaterial color="#38bdf8" transparent opacity={0.7} />
          </mesh>
        ))}

        {/* ============================================================== */}
        {/* MULTI-TIERED COMPUTATIONAL TOWERS                              */}
        {/* ============================================================== */}
        {towers.map((t, idx) => (
          <mesh key={`tower-${idx}`} position={t.pos} scale={t.scale}>
            <boxGeometry />
            <meshStandardMaterial
              color={t.color}
              metalness={t.metalness}
              roughness={t.roughness}
            />
          </mesh>
        ))}

        {/* ============================================================== */}
        {/* HIGH-ALTITUDE SUSPENDED SKYBRIDGES                             */}
        {/* ============================================================== */}
        {bridges.map((b, idx) => (
          <mesh key={`bridge-${idx}`} position={b.pos} scale={b.scale}>
            <boxGeometry />
            <meshStandardMaterial
              color="#1c304e"
              roughness={0.22}
              metalness={0.88}
              emissive="#0a172a"
              emissiveIntensity={0.25}
            />
          </mesh>
        ))}

        {/* Illuminated Cyan Guide Rails along Skybridges */}
        <mesh position={[0, 16.8, -44.3]}>
          <boxGeometry args={[75, 0.05, 0.05]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.75} />
        </mesh>
        <mesh position={[0, 6.8, -44.3]}>
          <boxGeometry args={[75, 0.05, 0.05]} />
          <meshBasicMaterial color="#6366f1" transparent opacity={0.75} />
        </mesh>

        {/* ============================================================== */}
        {/* SERVER RACK MICRO-INDICATORS                                   */}
        {/* ============================================================== */}
        {serverLights.map((l, idx) => (
          <mesh key={`srv-light-${idx}`} position={l.pos}>
            <boxGeometry args={[0.08, 0.035, 0.035]} />
            <meshBasicMaterial
              color={l.color}
              transparent
              opacity={isBuilding ? 0.9 : 0.65}
            />
          </mesh>
        ))}
      </group>
    </>
  );
};

// =====================================================================
// 2. SOPHISTICATED COMPUTATIONAL DECK / FLOOR
// Features: Dark metallic segmented deck tiles, recessed illuminated data
// channels, concentric orbital alignment tracks, and subtle reflections
// =====================================================================
const ComputationalDeck: React.FC<{ isBuilding: boolean }> = ({ isBuilding }) => {
  return (
    <group position={[0, -4.75, 0]}>
      {/* 1. Dark Metallic Titanium Floor Deck */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[180, 180]} />
        <meshStandardMaterial
          color="#0c172a"
          roughness={0.28}
          metalness={0.85}
          emissive="#060c18"
          emissiveIntensity={0.3}
        />
      </mesh>

      {/* 2. Recessed Cardinal Illuminated Data Channels (radiating from core) */}
      {[0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2].map((angle, idx) => (
        <group key={`floor-channel-${idx}`} rotation={[0, angle, 0]}>
          <mesh position={[24, 0.015, 0]}>
            <planeGeometry args={[44, 0.08]} />
            <meshBasicMaterial
              color="#38bdf8"
              transparent
              opacity={isBuilding ? 0.75 : 0.45}
            />
          </mesh>
          <mesh position={[24, 0.012, 0.35]}>
            <planeGeometry args={[44, 0.02]} />
            <meshBasicMaterial color="#1e3a5f" transparent opacity={0.4} />
          </mesh>
          <mesh position={[24, 0.012, -0.35]}>
            <planeGeometry args={[44, 0.02]} />
            <meshBasicMaterial color="#1e3a5f" transparent opacity={0.4} />
          </mesh>
        </group>
      ))}

      {/* 3. Concentric Orbital Alignment Tracks beneath Core */}
      {[3.8, 6.2, 9.8, 14.5, 21.0].map((radius, idx) => (
        <mesh key={`deck-ring-${idx}`} position={[0, 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[radius, radius + (idx % 2 === 0 ? 0.06 : 0.03), 80]} />
          <meshBasicMaterial
            color={idx === 0 ? '#38bdf8' : idx === 2 ? '#6366f1' : '#1e40af'}
            transparent
            opacity={isBuilding ? 0.6 : 0.3}
          />
        </mesh>
      ))}

      {/* 4. Fine Technical Coordinate Reference Grid (Very subdued, NOT a loud demo grid) */}
      <gridHelper
        args={[140, 48, '#1d3557', '#0e1e34']}
        position={[0, 0.025, 0]}
      />
    </group>
  );
};

// =====================================================================
// 3. NEAR FOREGROUND LAYER: Floating Optical Dust & Restrained Crystals
// =====================================================================
const NearForeground: React.FC = () => {
  const groupRef = useRef<THREE.Group>(null);

  const shards = useMemo(() => {
    const list: { pos: THREE.Vector3; speed: number }[] = [];
    for (let i = 0; i < 8; i++) {
      list.push({
        pos: new THREE.Vector3(
          (Math.random() - 0.5) * 8.5,
          (Math.random() - 0.5) * 4.5,
          2.2 + Math.random() * 2.8
        ),
        speed: 0.2 + Math.random() * 0.2,
      });
    }
    return list;
  }, []);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const t = state.clock.getElapsedTime();

    groupRef.current.position.x = state.pointer.x * 0.22;
    groupRef.current.position.y = state.pointer.y * 0.16;

    groupRef.current.children.forEach((child, i) => {
      const s = shards[i];
      if (s) {
        child.rotation.x += delta * 0.18;
        child.rotation.y += delta * 0.24;
        child.position.y = s.pos.y + Math.sin(t * s.speed + i) * 0.06;
      }
    });
  });

  return (
    <group ref={groupRef}>
      {shards.map((s, idx) => (
        <mesh key={`near-shard-${idx}`} position={s.pos} scale={[0.028, 0.028, 0.028]}>
          <octahedronGeometry />
          <meshStandardMaterial
            color="#e0f2fe"
            emissive="#38bdf8"
            emissiveIntensity={0.45}
            transparent
            opacity={0.35}
            roughness={0.15}
            metalness={0.9}
          />
        </mesh>
      ))}
    </group>
  );
};

// =====================================================================
// 4. CINEMATIC MULTI-TIER LIGHTING RIG
// Implements:
// 1. Large soft blue/indigo environmental fill (illuminates distant architecture)
// 2. Subtle cyan practical lights embedded inside structures
// 3. Cool white key directional illumination (reveals core & metallic bevels)
// 4. Soft violet/indigo secondary light (color separation)
// 5. Floor/deck illumination
// 6. Calibrated atmospheric fog
// =====================================================================
const CinematicLightingRig: React.FC<{
  phase: string;
  isBuilding: boolean;
  isComplete: boolean;
  stateColor: string;
}> = ({ phase, isBuilding, isComplete, stateColor }) => {
  const keyLightRef = useRef<THREE.DirectionalLight>(null);
  const spotLightRef = useRef<THREE.SpotLight>(null);

  useFrame((state) => {
    // Subtle pointer glancing specularity
    if (keyLightRef.current) {
      keyLightRef.current.position.x = 12 + state.pointer.x * 0.8;
      keyLightRef.current.position.y = 18 + state.pointer.y * 0.5;
    }

    // Active component localized spotlight tracking
    if (spotLightRef.current) {
      if (phase === 'DEBUG') {
        spotLightRef.current.target.position.set(-2.65, 0, 0);
        spotLightRef.current.color.set('#f59e0b');
        spotLightRef.current.intensity = 3.2;
      } else if (phase === 'BUILD') {
        spotLightRef.current.target.position.set(1.35, 0, 0);
        spotLightRef.current.color.set('#e0f2fe');
        spotLightRef.current.intensity = 2.8;
      } else if (phase === 'TEST' || phase === 'REVIEW') {
        spotLightRef.current.target.position.set(0, Math.sin(state.clock.getElapsedTime() * 2) * 1.5, 0);
        spotLightRef.current.color.set('#38bdf8');
        spotLightRef.current.intensity = 2.6;
      } else if (isComplete || phase === 'COMPLETE') {
        spotLightRef.current.target.position.set(0, 0.4, 0);
        spotLightRef.current.color.set('#f8fafc');
        spotLightRef.current.intensity = 3.2;
      } else {
        spotLightRef.current.target.position.set(0, 0.2, 0);
        spotLightRef.current.color.set('#cbd5e1');
        spotLightRef.current.intensity = 1.8;
      }
      spotLightRef.current.target.updateMatrixWorld();
    }
  });

  return (
    <>
      {/* 1. Large Soft Midnight-Blue Environmental Fill (Lifts pure black shadows) */}
      <ambientLight intensity={1.45} color="#183158" />

      {/* 2. Hemisphere Sky/Ground Light for Rich Color Transition */}
      <hemisphereLight args={['#254b85', '#081426', 1.35]} />

      {/* 3. Cool White Key Directional Light (Crisp specular sheen on metallic bevels) */}
      <directionalLight
        ref={keyLightRef}
        position={[12, 20, 14]}
        intensity={2.6}
        color="#ffffff"
      />

      {/* 4. Soft Violet/Indigo Secondary Light (Crucial Color Separation) */}
      <directionalLight
        position={[-16, 12, -8]}
        intensity={2.0}
        color="#6366f1"
      />

      {/* 5. Electric Cyan Rear Architectural Rim Light */}
      <directionalLight
        position={[0, 18, -20]}
        intensity={1.85}
        color="#38bdf8"
      />

      {/* 6. Slate Fill for Side Shadow Readability */}
      <directionalLight position={[8, -3, 8]} intensity={0.8} color="#94a3b8" />

      {/* 7. Underside Chassis Bounce Fill */}
      <directionalLight position={[0, -10, 4]} intensity={1.2} color="#1e3a68" />

      {/* 8. Floor Deck Localized Point Light */}
      <pointLight
        position={[0, -4.2, 0]}
        intensity={2.2}
        color="#0284c7"
        distance={28}
      />

      {/* 9. Reactive Core Point Light */}
      <pointLight
        position={[0, 0, 0]}
        intensity={isComplete ? 3.0 : isBuilding ? 2.8 : 1.6}
        color={stateColor}
        distance={22}
      />

      {/* 10. Focused Active Component Spotlight */}
      <spotLight
        ref={spotLightRef}
        position={[0, 8.5, 5.0]}
        angle={0.8}
        penumbra={0.7}
        intensity={2.0}
      />
    </>
  );
};

export const World3D: React.FC<World3DProps> = ({ state, scrollProgress, onSelectAgent }) => {
  const [hasWebGL, setHasWebGL] = useState(true);

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      setHasWebGL(Boolean(gl));
    } catch {
      setHasWebGL(false);
    }
  }, []);

  const isComplete = state.current_phase === 'COMPLETE' || Boolean(state.project_success);
  const isBuilding =
    state.is_running ||
    ['PLAN', 'ARCHITECT', 'BUILD', 'DEBUG', 'TEST', 'RUN', 'REVIEW'].includes(
      state.current_phase
    );

  // Controlled responsive state point light color
  const stateColor = useMemo(() => {
    if (state.current_phase === 'DEBUG') return '#f59e0b';
    if (isComplete) return '#10b981';
    if (state.current_phase === 'FAILED') return '#ef4444';
    if (isBuilding) return '#38bdf8';
    return '#60a5fa';
  }, [state.current_phase, isComplete, isBuilding]);

  if (!hasWebGL) {
    return <FallbackCanvas phase={state.current_phase} progress={state.progress_percent} />;
  }

  return (
    <div
      className="fixed inset-0 w-full h-full pointer-events-auto z-0"
      style={{
        background:
          'radial-gradient(ellipse at 50% 30%, #152d54 0%, #0d1e3a 40%, #081326 75%, #050d1a 100%)',
      }}
    >
      <Canvas
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        dpr={[1, Math.min(typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1, 1.5)]}
        camera={{ position: [0, 1.6, 9.4], fov: 44 }}
      >
        <CinematicCamera
          phase={state.current_phase}
          scrollProgress={scrollProgress}
          isBuilding={isBuilding}
          isComplete={isComplete}
        />

        {/* ============================================================== */}
        {/* 1. CINEMATIC MULTI-TIER LIGHTING RIG                          */}
        {/* ============================================================== */}
        <CinematicLightingRig
          phase={state.current_phase}
          isBuilding={isBuilding}
          isComplete={isComplete}
          stateColor={stateColor}
        />

        {/* Deep Atmospheric Midnight-Blue Fog with smooth linear falloff */}
        <fog attach="fog" args={['#0c1b36', 32, 145]} />

        {/* ============================================================== */}
        {/* 2. THREE INDEPENDENT SPATIAL DEPTH LAYERS                      */}
        {/* ============================================================== */}
        {/* BACKGROUND: Quantum Halo Ring, Overhead Arches & Faceted Towers */}
        <MonumentalBackground isBuilding={isBuilding} />

        {/* FLOOR: Segmented Metallic Deck, Recessed Channels & Alignment Rings */}
        <ComputationalDeck isBuilding={isBuilding} />

        {/* CENTRAL ARCHITECTURAL CORE: The Computational Architecture Core */}
        <ComputationalMachine
          state={state}
          scrollProgress={scrollProgress}
        />

        {/* Physical 3D Data Conduits & Travelling Packets */}
        <DataStreams activeAgent={state.active_agent} isBuilding={isBuilding} isComplete={isComplete} />

        {/* FOREGROUND: Subtle Optical Fragments & Dust */}
        <NearForeground />

        {/* Active Agent Constellation Indicator */}
        <AgentConstellation
          activeAgent={state.active_agent}
          activeStatus={state.active_agent_status}
          scrollProgress={scrollProgress}
          isBuilding={isBuilding}
        />
      </Canvas>
    </div>
  );
};
