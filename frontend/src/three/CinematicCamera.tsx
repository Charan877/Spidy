import React, { useRef, useMemo } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

interface CinematicCameraProps {
  phase: string;
  scrollProgress: number; // 0.0 to 1.0 (continuous across 8 stages)
  isBuilding: boolean;
  isComplete?: boolean;
}

export const CinematicCamera: React.FC<CinematicCameraProps> = ({
  phase,
  scrollProgress,
  isBuilding,
  isComplete = false,
}) => {
  const { camera, pointer } = useThree();
  const currentLookAt = useRef(new THREE.Vector3(0, 0, 0));

  // Curated 8-stage film-choreographed camera spline:
  // Establishes scale (Wide) -> input bus glide -> rail topology (Medium) -> assembly deck close-up (Close) ->
  // vertical power surge -> diagnostic recovery zoom (Close) -> canopy convergence -> stabilized monument pullback
  const getScrollWaypoints = (p: number) => {
    const waypoints = [
      // 00 INTRO: Wide establishing shot of the computational cathedral
      { pos: new THREE.Vector3(0, 1.7, 9.2), lookAt: new THREE.Vector3(0, 0.35, 0) },

      // 01 DESTRUCTURING: Gentle glide to the right showing input conduits
      { pos: new THREE.Vector3(1.8, 1.2, 8.2), lookAt: new THREE.Vector3(0, 0.2, 0) },

      // 02 TOPOLOGY: High architectural angle observing magnetic rails & topology
      { pos: new THREE.Vector3(-2.4, 2.6, 7.8), lookAt: new THREE.Vector3(0, 0.3, 0) },

      // 03 SYNTHESIS: Medium vantage into assembly deck watching modular pods & internal wafers
      { pos: new THREE.Vector3(2.2, 1.1, 7.0), lookAt: new THREE.Vector3(0, 0.1, 0) },

      // 04 PROBING: Low angle viewing vertical power trunk and halo ring
      { pos: new THREE.Vector3(0.8, -0.2, 6.8), lookAt: new THREE.Vector3(0, 0.4, 0) },

      // 05 RECOVERY: Left vantage viewing ejected diagnostic pod on -X rail
      { pos: new THREE.Vector3(-2.2, 1.0, 7.0), lookAt: new THREE.Vector3(0, 0.1, 0) },

      // 06 CONVERGENCE: Elevated angle viewing overhead verification canopy & optical prisms
      { pos: new THREE.Vector3(0, 2.2, 8.0), lookAt: new THREE.Vector3(0, 0.8, 0) },

      // 07 RESULT: Grand panoramic pullback revealing the fully stabilized computational monument
      { pos: new THREE.Vector3(0, 1.6, 11.5), lookAt: new THREE.Vector3(0, 0.3, 0) },
    ];

    const clampedP = Math.max(0, Math.min(1, p));
    const segmentCount = waypoints.length - 1;
    const scaledP = clampedP * segmentCount;
    const index = Math.min(Math.floor(scaledP), segmentCount - 1);
    const frac = scaledP - index;

    // Smooth cubic Hermite interpolation
    const ease = frac * frac * (3 - 2 * frac);

    const from = waypoints[index];
    const to = waypoints[index + 1];

    const pos = new THREE.Vector3().lerpVectors(from.pos, to.pos, ease);
    const lookAt = new THREE.Vector3().lerpVectors(from.lookAt, to.lookAt, ease);

    return { pos, lookAt };
  };

  // Real backend phase camera focus choreography during active builds
  const getBuildPhaseTarget = () => {
    switch (phase) {
      case 'PLAN':
      case 'ARCHITECT':
        return { pos: new THREE.Vector3(-2.4, 2.6, 7.8), lookAt: new THREE.Vector3(0, 0.3, 0) };
      case 'BUILD':
        return { pos: new THREE.Vector3(2.2, 1.1, 7.0), lookAt: new THREE.Vector3(0, 0.1, 0) };
      case 'DEBUG':
        return { pos: new THREE.Vector3(-2.2, 1.0, 7.0), lookAt: new THREE.Vector3(0, 0.1, 0) };
      case 'TEST':
      case 'REVIEW':
        return { pos: new THREE.Vector3(1.8, 1.2, 7.5), lookAt: new THREE.Vector3(0, 0.2, 0) };
      case 'RUN':
        return { pos: new THREE.Vector3(0.8, -0.2, 6.8), lookAt: new THREE.Vector3(0, 0.4, 0) };
      case 'COMPLETE':
        return { pos: new THREE.Vector3(0, 1.6, 11.5), lookAt: new THREE.Vector3(0, 0.3, 0) };
      default:
        return getScrollWaypoints(scrollProgress);
    }
  };

  const prefersReducedMotion = useMemo(() => {
    return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  useFrame((state, delta) => {
    const t = state.clock.getElapsedTime();
    const { pos: basePos, lookAt: baseLookAt } =
      isComplete || phase === 'COMPLETE'
        ? { pos: new THREE.Vector3(0, 1.8, 13.0), lookAt: new THREE.Vector3(0, 0.3, 0) }
        : isBuilding
        ? getBuildPhaseTarget()
        : getScrollWaypoints(scrollProgress);

    if (prefersReducedMotion) {
      camera.position.lerp(basePos, delta * 3.0);
      currentLookAt.current.lerp(baseLookAt, delta * 3.0);
      camera.lookAt(currentLookAt.current);
      return;
    }

    // Idle organic floating Lissajous drift when calm
    const idleDriftX = isBuilding ? 0 : Math.sin(t * 0.25) * 0.14;
    const idleDriftY = isBuilding ? 0 : Math.cos(t * 0.38) * 0.08;

    // Subtle cinematic mouse parallax
    const parallaxX = pointer.x * 0.24;
    const parallaxY = pointer.y * 0.16;

    // Micro-jitter during active debug recovery
    const jitterX = phase === 'DEBUG' ? (Math.random() - 0.5) * 0.03 : 0;
    const jitterY = phase === 'DEBUG' ? (Math.random() - 0.5) * 0.03 : 0;

    const targetPos = new THREE.Vector3(
      basePos.x + parallaxX + jitterX + idleDriftX,
      basePos.y + parallaxY + jitterY + idleDriftY,
      basePos.z
    );

    const targetLookAt = new THREE.Vector3(
      baseLookAt.x + pointer.x * 0.15,
      baseLookAt.y + pointer.y * 0.1,
      baseLookAt.z
    );

    // Damped camera transition
    camera.position.lerp(targetPos, delta * 2.8);
    currentLookAt.current.lerp(targetLookAt, delta * 3.2);
    camera.lookAt(currentLookAt.current);
    camera.rotation.z = pointer.x * -0.01;
  });

  return null;
};
