import React, { useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';

interface DataStreamsProps {
  activeAgent: string;
  isBuilding: boolean;
  isComplete?: boolean;
}

const STREAM_PARTICLE_COUNT = 240;
const PHYSICAL_PACKET_COUNT = 16;

export const DataStreams: React.FC<DataStreamsProps> = ({ activeAgent, isBuilding, isComplete = false }) => {
  const pointsRef = useRef<THREE.Points>(null);
  const packetsGroupRef = useRef<THREE.Group>(null);

  // Define 8 orthogonal computational bus paths
  // Each path consists of 4 3D waypoints: entry -> junction -> spine entry -> riser
  const busRoutes = useMemo(() => {
    return [
      // 0: +X input ingestion bus
      [new THREE.Vector3(5.4, -2.34, 0), new THREE.Vector3(2.6, -2.34, 0), new THREE.Vector3(1.3, -1.8, 0), new THREE.Vector3(0, 2.0, 0)],
      // 1: -X input ingestion bus
      [new THREE.Vector3(-5.4, -2.34, 0), new THREE.Vector3(-2.6, -2.34, 0), new THREE.Vector3(-1.3, -1.8, 0), new THREE.Vector3(0, 2.0, 0)],
      // 2: +Z input ingestion bus
      [new THREE.Vector3(0, -2.34, 5.4), new THREE.Vector3(0, -2.34, 2.6), new THREE.Vector3(0, -1.8, 1.3), new THREE.Vector3(0, 2.0, 0)],
      // 3: -Z input ingestion bus
      [new THREE.Vector3(0, -2.34, -5.4), new THREE.Vector3(0, -2.34, -2.6), new THREE.Vector3(0, -1.8, -1.3), new THREE.Vector3(0, 2.0, 0)],
      // 4: Internal vertical logic bus distribution
      [new THREE.Vector3(0, -2.2, 0), new THREE.Vector3(0, -0.6, 0), new THREE.Vector3(0, 0.8, 0), new THREE.Vector3(0, 2.3, 0)],
      // 5: Canopy verification return loop
      [new THREE.Vector3(0, 2.3, 0), new THREE.Vector3(1.2, 2.3, 0), new THREE.Vector3(1.4, 0.0, 0), new THREE.Vector3(0, -2.3, 0)],
      // 6: Lateral compilation bridge between pod tiers
      [new THREE.Vector3(1.8, 1.15, 0), new THREE.Vector3(0, 1.15, 1.8), new THREE.Vector3(-1.8, 1.15, 0), new THREE.Vector3(0, 1.15, -1.8)],
      // 7: Substrate return conduit
      [new THREE.Vector3(-1.4, -1.15, 0), new THREE.Vector3(0, -1.15, -1.4), new THREE.Vector3(1.4, -1.15, 0), new THREE.Vector3(0, -2.4, 0)],
    ];
  }, []);

  // Precompute smooth 3D spline curves for physical optical tubes
  const curves = useMemo(() => {
    return busRoutes.map((points) => new THREE.CatmullRomCurve3(points, false, 'catmullrom', 0.1));
  }, [busRoutes]);

  // Precompute 3D tube geometries for physical conduits
  const tubeGeometries = useMemo(() => {
    return curves.map((curve) => new THREE.TubeGeometry(curve, 32, 0.022, 6, false));
  }, [curves]);

  // Optical tube glass material with subtle specular reflection
  const tubeMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#081426',
      roughness: 0.15,
      metalness: 0.35,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
    });
  }, []);

  // Physical data packet material (traveling through tubes)
  const packetMaterial = useMemo(() => {
    return new THREE.MeshStandardMaterial({
      color: '#e0f2fe',
      emissive: '#38bdf8',
      emissiveIntensity: 0.65,
      roughness: 0.2,
      metalness: 0.9,
    });
  }, []);

  // Packet state metadata
  const packetConfigs = useMemo(() => {
    return Array.from({ length: PHYSICAL_PACKET_COUNT }, (_, i) => ({
      id: i,
      routeIndex: i % 8,
      offset: i / PHYSICAL_PACKET_COUNT,
      baseSpeed: 0.22 + (i % 5) * 0.06,
    }));
  }, []);

  // Precompute initial progress offsets and assigned routes for particle pulses
  const { positions, routeIndices, progressOffsets, speeds } = useMemo(() => {
    const pos = new Float32Array(STREAM_PARTICLE_COUNT * 3);
    const rIndices = new Uint8Array(STREAM_PARTICLE_COUNT);
    const pOffsets = new Float32Array(STREAM_PARTICLE_COUNT);
    const sp = new Float32Array(STREAM_PARTICLE_COUNT);

    for (let i = 0; i < STREAM_PARTICLE_COUNT; i++) {
      rIndices[i] = i % 8;
      pOffsets[i] = i / STREAM_PARTICLE_COUNT;
      sp[i] = 0.28 + (i % 7) * 0.12;
    }

    return { positions: pos, routeIndices: rIndices, progressOffsets: pOffsets, speeds: sp };
  }, []);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    const agentLower = (activeAgent || '').toLowerCase();

    // 1. Update Physical Traveling Data Packets
    if (packetsGroupRef.current) {
      const isTestOrReview = agentLower.includes('review') || agentLower.includes('test');
      const isDebugState = agentLower.includes('debug');

      packetsGroupRef.current.children.forEach((child, i) => {
        const config = packetConfigs[i];
        if (!config) return;

        const curve = curves[config.routeIndex];
        let speedMult = isBuilding ? 1.8 : 0.6;
        if (isTestOrReview) speedMult = 1.2;
        if (isComplete) speedMult = 0.22;

        const u = (config.offset + t * config.baseSpeed * speedMult * 0.18) % 1.0;
        const pt = curve.getPointAt(u);
        child.position.copy(pt);

        // Subtly rotate packet as it travels
        child.rotation.x = t * (isComplete ? 0.8 : 2) + i;
        child.rotation.y = t * (isComplete ? 1.2 : 3) + i;

        // Packet size and color response
        const mesh = child as THREE.Mesh;
        const mat = mesh.material as THREE.MeshStandardMaterial;
        if (mat) {
          if (isComplete) {
            mat.emissive.set('#10b981');
            mat.emissiveIntensity = 0.65;
          } else if (isDebugState && config.routeIndex === 1) {
            mat.emissive.set('#f59e0b');
            mat.emissiveIntensity = 0.9;
          } else if (isTestOrReview) {
            mat.emissive.set('#10b981');
            mat.emissiveIntensity = 0.75;
          } else {
            mat.emissive.set(isBuilding ? '#38bdf8' : '#64748b');
            mat.emissiveIntensity = isBuilding ? 0.65 : 0.25;
          }
        }
      });
    }

    // 2. Update Inner Optical Particle Pulses
    if (pointsRef.current) {
      const geo = pointsRef.current.geometry;
      const posAttr = geo.attributes.position as THREE.BufferAttribute;
      const arr = posAttr.array as Float32Array;

      for (let i = 0; i < STREAM_PARTICLE_COUNT; i++) {
        const idx = i * 3;
        const routeIdx = routeIndices[i];
        const curve = curves[routeIdx];

        let routeSpeedFactor = 1.0;
        if (isComplete) {
          routeSpeedFactor = 0.35;
        } else if (routeIdx <= 3) {
          routeSpeedFactor = agentLower.includes('plan') ? 2.2 : isBuilding ? 1.3 : 0.55;
        } else if (routeIdx === 4 || routeIdx === 5) {
          routeSpeedFactor = isBuilding ? 2.0 : 0.75;
        } else if (routeIdx === 6) {
          routeSpeedFactor = isBuilding ? 2.5 : 0.9;
        } else {
          routeSpeedFactor = agentLower.includes('review') || agentLower.includes('test') ? 1.8 : 0.65;
        }

        const u = (progressOffsets[i] + t * speeds[i] * routeSpeedFactor * 0.18) % 1.0;
        const pt = curve.getPointAt(u);

        arr[idx] = pt.x;
        arr[idx + 1] = pt.y;
        arr[idx + 2] = pt.z;
      }
      posAttr.needsUpdate = true;

      const mat = pointsRef.current.material as THREE.PointsMaterial;
      if (mat) {
        const targetOpacity = isBuilding ? 0.72 : 0.32;
        mat.opacity += (targetOpacity - mat.opacity) * 0.05;
        const targetSize = isBuilding ? 0.038 : 0.026;
        mat.size += (targetSize - mat.size) * 0.05;

        let hexColor = isBuilding ? '#38bdf8' : '#64748b';
        if (agentLower.includes('debug')) hexColor = '#f59e0b';
        else if (agentLower.includes('review') || agentLower.includes('test')) hexColor = '#10b981';

        mat.color.lerp(new THREE.Color(hexColor), 0.05);
      }
    }
  });

  return (
    <group>
      {/* 1. Physical 3D Optical Conduit Tubes */}
      {tubeGeometries.map((geo, idx) => (
        <mesh key={`tube-${idx}`} geometry={geo} material={tubeMaterial} />
      ))}

      {/* 2. Physical Data Packets Traveling Inside Tubes */}
      <group ref={packetsGroupRef}>
        {packetConfigs.map((cfg) => (
          <mesh key={`packet-${cfg.id}`} material={packetMaterial}>
            <octahedronGeometry args={[0.032, 0]} />
          </mesh>
        ))}
      </group>

      {/* 3. Inner Light Pulse Core Particles */}
      <points ref={pointsRef} key="spidy-orthogonal-data-streams">
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={STREAM_PARTICLE_COUNT}
            array={positions}
            itemSize={3}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.032}
          color="#38bdf8"
          transparent
          opacity={0.35}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
    </group>
  );
};
