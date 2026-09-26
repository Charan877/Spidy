import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface CentralCoreProps {
  phase: string;
  progress: number; // 0 - 100
  filesCount: number;
}

export const CentralCore: React.FC<CentralCoreProps> = ({ phase, progress, filesCount }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const wireRef = useRef<THREE.LineSegments>(null);
  const innerRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Group>(null);

  // Palette based on phase
  const getPhaseColor = () => {
    switch (phase) {
      case 'PLAN':
      case 'ARCHITECT':
        return new THREE.Color('#38bdf8'); // Sky Cyan
      case 'BUILD':
        return new THREE.Color('#818cf8'); // Indigo
      case 'DEBUG':
        return new THREE.Color('#f43f5e'); // Rose
      case 'TEST':
      case 'REVIEW':
      case 'VERIFY':
      case 'RUN':
        return new THREE.Color('#10b981'); // Emerald
      case 'COMPLETE':
        return new THREE.Color('#34d399'); // Glowing Jade
      default:
        return new THREE.Color('#6366f1'); // Primary Iris
    }
  };

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    const targetColor = getPhaseColor();

    if (meshRef.current) {
      // Rotation speed depends on phase
      const rotSpeed = phase === 'BUILD' ? 0.8 : phase === 'DEBUG' ? 1.4 : 0.25;
      meshRef.current.rotation.y += delta * rotSpeed;
      meshRef.current.rotation.x = Math.sin(t * 0.4) * 0.15;

      // Scale grows slightly with task progress and generated files
      const growth = 1 + (progress / 100) * 0.4 + Math.min(filesCount * 0.02, 0.3);
      const pulse = phase === 'DEBUG' ? Math.sin(t * 8) * 0.08 : Math.sin(t * 2) * 0.03;
      const targetScale = growth + pulse;
      meshRef.current.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.05);

      // Lerp material color
      const mat = meshRef.current.material as THREE.MeshStandardMaterial;
      if (mat) {
        mat.color.lerp(targetColor, 0.05);
        mat.emissive.lerp(targetColor, 0.05);
        mat.emissiveIntensity = phase === 'COMPLETE' ? 0.6 : phase === 'BUILD' ? 0.4 : 0.2;
      }
    }

    if (wireRef.current) {
      wireRef.current.rotation.y -= delta * 0.3;
      wireRef.current.rotation.z += delta * 0.1;
    }

    if (innerRef.current) {
      innerRef.current.rotation.y += delta * 0.5;
      innerRef.current.rotation.x -= delta * 0.3;
    }

    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.15;
      ringRef.current.rotation.x = Math.PI / 3 + Math.sin(t * 0.5) * 0.1;
    }
  });

  return (
    <group position={[0, 0, 0]}>
      {/* Outer crystalline faceted polyhedron */}
      <mesh ref={meshRef}>
        <icosahedronGeometry args={[1.8, 1]} />
        <meshStandardMaterial
          roughness={0.15}
          metalness={0.85}
          transparent
          opacity={0.88}
          wireframe={phase === 'PLAN' || phase === 'ARCHITECT'}
        />
      </mesh>

      {/* Internal dense computational core */}
      <mesh ref={innerRef}>
        <dodecahedronGeometry args={[0.9, 0]} />
        <meshStandardMaterial
          roughness={0.1}
          metalness={0.9}
          color="#38bdf8"
          emissive="#6366f1"
          emissiveIntensity={0.8}
        />
      </mesh>

      {/* Floating orbital resonance rings */}
      <group ref={ringRef}>
        <mesh>
          <torusGeometry args={[2.7, 0.02, 16, 100]} />
          <meshBasicMaterial color="#818cf8" transparent opacity={0.4} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[3.2, 0.015, 16, 100]} />
          <meshBasicMaterial color="#38bdf8" transparent opacity={0.25} />
        </mesh>
      </group>
    </group>
  );
};
