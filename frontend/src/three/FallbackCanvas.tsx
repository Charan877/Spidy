import React, { useEffect, useRef } from 'react';

interface FallbackCanvasProps {
  phase: string;
  progress: number;
}

export const FallbackCanvas: React.FC<FallbackCanvasProps> = ({ phase, progress }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;
    let angle = 0;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const render = () => {
      angle += 0.01;
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;

      ctx.clearRect(0, 0, w, h);

      // Background ambient gradient
      const grad = ctx.createRadialGradient(cx, cy, 50, cx, cy, Math.max(w, h) * 0.7);
      grad.addColorStop(0, 'rgba(15, 23, 42, 0.8)');
      grad.addColorStop(1, 'rgba(4, 7, 17, 1)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      // Central crystalline representation
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angle * 0.5);

      const color = phase === 'COMPLETE' ? '#10b981' : phase === 'BUILD' ? '#818cf8' : '#38bdf8';
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.5;

      const size = 90 + (progress / 100) * 30;
      for (let i = 0; i < 6; i++) {
        const a = (i * Math.PI) / 3;
        const x = Math.cos(a) * size;
        const y = Math.sin(a) * size;
        if (i === 0) ctx.beginPath();
        ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();

      // Orbital rings
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.12)';
      ctx.beginPath();
      ctx.arc(0, 0, size * 1.6, 0, Math.PI * 2);
      ctx.stroke();

      ctx.restore();

      animId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, [phase, progress]);

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" />;
};
