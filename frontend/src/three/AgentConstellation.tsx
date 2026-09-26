import React, { useRef, useMemo } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

interface AgentDef {
  id: string;
  name: string;
  role: string;
  position: [number, number, number];
  color: string;
}

const AGENT_CATALOG: Record<string, AgentDef> = {
  planner: {
    id: 'planner',
    name: 'PLANNER',
    role: 'Scoping & Intent',
    position: [0, 3.2, 0.5],
    color: '#38bdf8',
  },
  architect: {
    id: 'architect',
    name: 'ARCHITECT',
    role: 'System Topology',
    position: [-3.2, 1.8, -0.4],
    color: '#60a5fa',
  },
  developer: {
    id: 'developer',
    name: 'DEVELOPER',
    role: 'Code Synthesis',
    position: [3.2, 1.4, 0.4],
    color: '#38bdf8',
  },
  tester: {
    id: 'tester',
    name: 'TESTER',
    role: 'Process & Health Gates',
    position: [2.8, -1.8, -0.3],
    color: '#06b6d4',
  },
  debugger: {
    id: 'debugger',
    name: 'DEBUGGER',
    role: 'Fault Containment',
    position: [-3.2, -1.6, 0.8],
    color: '#f59e0b',
  },
  reviewer: {
    id: 'reviewer',
    name: 'REVIEWER',
    role: 'Six-Gate Verification',
    position: [0, -3.0, 0.4],
    color: '#10b981',
  },
};

interface AgentConstellationProps {
  activeAgent: string;
  activeStatus: string;
  scrollProgress?: number;
  isBuilding?: boolean;
}

export const AgentConstellation: React.FC<AgentConstellationProps> = ({
  activeAgent,
  activeStatus,
  scrollProgress = 0,
  isBuilding = false,
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);
  const conduitRef = useRef<THREE.Line>(null);

  // Determine exactly ONE active agent based on build state or scroll progression
  const currentAgent = useMemo<AgentDef | null>(() => {
    if (isBuilding) {
      const lower = (activeAgent || '').toLowerCase();
      if (lower.includes('plan')) return AGENT_CATALOG.planner;
      if (lower.includes('arch')) return AGENT_CATALOG.architect;
      if (lower.includes('build') || lower.includes('dev')) return AGENT_CATALOG.developer;
      if (lower.includes('test')) return AGENT_CATALOG.tester;
      if (lower.includes('debug')) return AGENT_CATALOG.debugger;
      if (lower.includes('review') || lower.includes('gate')) return AGENT_CATALOG.reviewer;
      return AGENT_CATALOG.developer;
    }

    const p = Math.max(0, Math.min(1, scrollProgress));
    if (p < 0.125) return null; // 00 INTRO: No active agent
    if (p < 0.25) return AGENT_CATALOG.planner; // 01 UNDERSTAND
    if (p < 0.375) return AGENT_CATALOG.architect; // 02 PLAN
    if (p < 0.50) return AGENT_CATALOG.developer; // 03 BUILD
    if (p < 0.625) return AGENT_CATALOG.tester; // 04 TEST
    if (p < 0.75) return AGENT_CATALOG.debugger; // 05 RECOVER
    if (p < 0.875) return AGENT_CATALOG.reviewer; // 06 VERIFY
    return null; // 07 RESULT: Stabilized monument
  }, [isBuilding, activeAgent, scrollProgress]);

  // Target position and color for the single active agent
  const targetPos = useMemo(() => {
    return currentAgent ? new THREE.Vector3(...currentAgent.position) : new THREE.Vector3(0, 10, 0);
  }, [currentAgent]);

  // Dynamic conduit curve connecting active agent to origin
  const conduitGeo = useMemo(() => {
    if (!currentAgent) return new THREE.BufferGeometry();
    const curve = new THREE.QuadraticBezierCurve3(
      new THREE.Vector3(...currentAgent.position),
      new THREE.Vector3(currentAgent.position[0] * 0.5, currentAgent.position[1] * 0.5, 0.6),
      new THREE.Vector3(0, 0, 0)
    );
    return new THREE.BufferGeometry().setFromPoints(curve.getPoints(24));
  }, [currentAgent]);

  const conduitMesh = useMemo(() => {
    return new THREE.Line(
      conduitGeo,
      new THREE.LineBasicMaterial({
        color: new THREE.Color(currentAgent?.color || '#38bdf8'),
        transparent: true,
        opacity: 0.6,
      })
    );
  }, [conduitGeo, currentAgent]);

  useFrame((state, delta) => {
    if (!groupRef.current) return;
    const t = state.clock.getElapsedTime();

    if (currentAgent) {
      // Smoothly glide to the active agent position
      groupRef.current.position.lerp(targetPos, 0.08);

      // Micro hovering
      groupRef.current.position.y += Math.sin(t * 2.5) * 0.003;

      if (meshRef.current) {
        // Unique motion signature per agent role
        let rotMultiplier = 1.2;
        let pulseFreq = 3.0;
        let pulseAmp = 0.08;

        if (currentAgent.id === 'developer') {
          rotMultiplier = 2.6; // High frequency compilation activity
          pulseFreq = 6.0;
          pulseAmp = 0.12;
        } else if (currentAgent.id === 'planner') {
          rotMultiplier = 0.7; // Deliberate scoping
          pulseFreq = 2.0;
          pulseAmp = 0.05;
        } else if (currentAgent.id === 'architect') {
          rotMultiplier = 1.0;
          pulseFreq = 2.5;
        } else if (currentAgent.id === 'tester') {
          rotMultiplier = 1.8;
          groupRef.current.position.y += Math.sin(t * 3.5) * 0.08; // Vertical scan sweep
        } else if (currentAgent.id === 'debugger') {
          rotMultiplier = 1.4;
          // Micro-jitter fault diagnostics
          groupRef.current.position.x += (Math.random() - 0.5) * 0.02;
        } else if (currentAgent.id === 'reviewer') {
          rotMultiplier = 0.9;
          pulseFreq = 2.2;
        }

        meshRef.current.rotation.y += delta * rotMultiplier;
        meshRef.current.rotation.x = Math.sin(t * 1.4) * 0.25;
        const s = 1.0 + Math.sin(t * pulseFreq) * pulseAmp;
        meshRef.current.scale.set(s, s, s);

        const mat = meshRef.current.material as THREE.MeshStandardMaterial;
        if (mat) {
          mat.color.lerp(new THREE.Color(currentAgent.color), 0.1);
          mat.emissive.lerp(new THREE.Color(currentAgent.color), 0.1);
          mat.emissiveIntensity = isBuilding ? 1.4 : 0.8;
        }
      }

      if (ringRef.current) {
        const ringSpeed = currentAgent.id === 'developer' ? 3.5 : 1.8;
        ringRef.current.rotation.z += delta * ringSpeed;
        ringRef.current.rotation.y = Math.PI / 3 + Math.sin(t * 1.5) * 0.2;
        const rMat = ringRef.current.material as THREE.MeshBasicMaterial;
        if (rMat) {
          rMat.color.lerp(new THREE.Color(currentAgent.color), 0.1);
        }
      }

      if (conduitMesh) {
        const cMat = conduitMesh.material as THREE.LineBasicMaterial;
        if (cMat) {
          cMat.color.lerp(new THREE.Color(currentAgent.color), 0.1);
          const conduitPulse = currentAgent.id === 'developer' ? Math.sin(t * 6) * 0.35 : Math.sin(t * 3) * 0.2;
          cMat.opacity = 0.55 + conduitPulse;
        }
      }
    }
  });

  if (!currentAgent) return null;

  return (
    <group ref={groupRef} position={targetPos}>
      {/* 1. Specialized Polyhedral Agent Entity */}
      <mesh ref={meshRef}>
        <octahedronGeometry args={[0.32, 0]} />
        <meshStandardMaterial
          roughness={0.15}
          metalness={0.9}
          color={currentAgent.color}
          emissive={currentAgent.color}
          emissiveIntensity={1.2}
        />
      </mesh>

      {/* 2. Concentric Orbiting Resonance Ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[0.52, 0.015, 12, 48]} />
        <meshBasicMaterial color={currentAgent.color} transparent opacity={0.7} />
      </mesh>

      {/* 3. Dynamic Connection Conduit to Machine */}
      <primitive
        object={conduitMesh}
        position={[-currentAgent.position[0], -currentAgent.position[1], -currentAgent.position[2]]}
      />

      {/* 4. Ultra-Minimal Editorial Spatial Indicator (Strictly ONE label) */}
      <Html distanceFactor={12} position={[0, -0.65, 0]} center pointerEvents="none">
        <div className="flex flex-col items-center select-none whitespace-nowrap">
          <div className="flex items-center gap-1.5 font-mono text-[10px] tracking-[0.25em] uppercase text-white font-bold bg-black/60 px-2 py-0.5 rounded border border-white/10 backdrop-blur-sm">
            <span
              className="w-1.5 h-1.5 rounded-full animate-ping"
              style={{ backgroundColor: currentAgent.color }}
            />
            <span>{currentAgent.name}</span>
          </div>
          <div className="font-mono text-[8px] tracking-wider text-slate-400 mt-0.5">
            {isBuilding && activeStatus ? activeStatus : currentAgent.role}
          </div>
        </div>
      </Html>
    </group>
  );
};
