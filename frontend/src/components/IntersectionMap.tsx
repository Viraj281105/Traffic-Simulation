import React, { useRef, useEffect } from 'react';
import type { SingleVehicleResponse, SimulationLifecycle } from '../types/simulation';

export interface IntersectionMapProps {
  vehicles: SingleVehicleResponse[];
  status?: SimulationLifecycle;
  width?: number;
  height?: number;
  lanesNorth?: number;
  lanesSouth?: number;
  lanesEast?: number;
  lanesWest?: number;
  laneWidth?: number;       // meters
  intersectionSize?: number; // meters (size of the central box)
  showCrosswalks?: boolean;
  showStopLines?: boolean;
  debug?: boolean;
  ppm?: number;              // pixels per meter
}

export const IntersectionMap: React.FC<IntersectionMapProps> = ({
  vehicles,
  status = 'stopped',
  width = 800,
  height = 600,
  lanesNorth = 2,
  lanesSouth = 2,
  lanesEast = 2,
  lanesWest = 2,
  laneWidth = 3.5,
  intersectionSize = 15,
  showCrosswalks = true,
  showStopLines = true,
  debug = false,
  ppm = 3.0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (debug) {
      console.log(`[IntersectionMap] Drawing frame. Active vehicles count: ${vehicles.length.toString()}`);
    }

    // Coordinate conversions: Center is (0,0) in world coordinates.
    // X goes East (+), West (-)
    // Y goes North (+), South (-)
    const worldToCanvas = (worldX: number, worldY: number): [number, number] => {
      const canvasX = worldX * ppm + width / 2;
      const canvasY = -worldY * ppm + height / 2;
      return [canvasX, canvasY];
    };

    // 1. Draw Background (Muted Green Shoulder)
    ctx.fillStyle = '#2e432e';
    ctx.fillRect(0, 0, width, height);

    // Geometry calculations
    const halfSize = intersectionSize / 2;

    const roadWidthN = lanesNorth * laneWidth;
    const roadWidthS = lanesSouth * laneWidth;
    const roadWidthE = lanesEast * laneWidth;
    const roadWidthW = lanesWest * laneWidth;

    // 2. Draw Roads (Dark Asphalt)
    ctx.fillStyle = '#1e1e24';

    // North Road
    const [nL, nTop] = worldToCanvas(-roadWidthN / 2, 100);
    const [nR, nBottom] = worldToCanvas(roadWidthN / 2, halfSize);
    ctx.fillRect(nL, nTop, nR - nL, nBottom - nTop);

    // South Road
    const [sL, sTop] = worldToCanvas(-roadWidthS / 2, -halfSize);
    const [sR, sBottom] = worldToCanvas(roadWidthS / 2, -100);
    ctx.fillRect(sL, sTop, sR - sL, sBottom - sTop);

    // East Road
    const [eL, eTop] = worldToCanvas(halfSize, roadWidthE / 2);
    const [eR, eBottom] = worldToCanvas(100, -roadWidthE / 2);
    ctx.fillRect(eL, eTop, eR - eL, eBottom - eTop);

    // West Road
    const [wL, wTop] = worldToCanvas(-100, roadWidthW / 2);
    const [wR, wBottom] = worldToCanvas(-halfSize, -roadWidthW / 2);
    ctx.fillRect(wL, wTop, wR - wL, wBottom - wTop);

    // Center Junction Box
    const [jL, jTop] = worldToCanvas(-halfSize, halfSize);
    const [jR, jBottom] = worldToCanvas(halfSize, -halfSize);
    ctx.fillRect(jL, jTop, jR - jL, jBottom - jTop);

    // 3. Draw Lane Markings & Center Divides
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;

    // Dash pattern for lane separations
    const dashLength = 4;
    const gapLength = 6;

    // Helper to draw lane dividers
    const drawDividers = (
      dir: 'N' | 'S' | 'E' | 'W',
      lanesCount: number,
      widthRoad: number,
      startDist: number,
      endDist: number
    ) => {
      ctx.save();
      for (let i = 1; i < lanesCount; i++) {
        // Offset from left edge of the road
        const offset = -widthRoad / 2 + i * laneWidth;
        // Muted white for lane dividers, yellow/double solid for center divide
        const isCenter = Math.abs(offset) < 0.1;
        if (isCenter) {
          ctx.strokeStyle = '#ffd166'; // Double yellow center divide
          ctx.lineWidth = 2.0;
          ctx.setLineDash([]);
        } else {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
          ctx.lineWidth = 1.0;
          ctx.setLineDash([dashLength, gapLength]);
        }

        ctx.beginPath();
        if (dir === 'N' || dir === 'S') {
          const mult = dir === 'N' ? 1 : -1;
          const [p1X, p1Y] = worldToCanvas(offset, startDist * mult);
          const [p2X, p2Y] = worldToCanvas(offset, endDist * mult);
          ctx.moveTo(p1X, p1Y);
          ctx.lineTo(p2X, p2Y);
        } else {
          const mult = dir === 'E' ? 1 : -1;
          const [p1X, p1Y] = worldToCanvas(startDist * mult, offset);
          const [p2X, p2Y] = worldToCanvas(endDist * mult, offset);
          ctx.moveTo(p1X, p1Y);
          ctx.lineTo(p2X, p2Y);
        }
        ctx.stroke();
      }
      ctx.restore();
    };

    // Draw dividers for approaches
    drawDividers('N', lanesNorth, roadWidthN, halfSize, 100);
    drawDividers('S', lanesSouth, roadWidthS, halfSize, 100);
    drawDividers('E', lanesEast, roadWidthE, halfSize, 100);
    drawDividers('W', lanesWest, roadWidthW, halfSize, 100);

    // 4. Draw Stop Lines / Yield Lines
    if (showStopLines) {
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3.0;

      // South Stop Line (incoming lanes: X > 0, at Y = -halfSize)
      ctx.beginPath();
      const [sS1X, sS1Y] = worldToCanvas(0, -halfSize);
      const [sS2X, sS2Y] = worldToCanvas(roadWidthS / 2, -halfSize);
      ctx.moveTo(sS1X, sS1Y);
      ctx.lineTo(sS2X, sS2Y);
      ctx.stroke();

      // North Stop Line (incoming lanes: X < 0, at Y = halfSize)
      ctx.beginPath();
      const [nS1X, nS1Y] = worldToCanvas(-roadWidthN / 2, halfSize);
      const [nS2X, nS2Y] = worldToCanvas(0, halfSize);
      ctx.moveTo(nS1X, nS1Y);
      ctx.lineTo(nS2X, nS2Y);
      ctx.stroke();

      // East Stop Line (incoming lanes: Y > 0, at X = halfSize)
      ctx.beginPath();
      const [eS1X, eS1Y] = worldToCanvas(halfSize, 0);
      const [eS2X, eS2Y] = worldToCanvas(halfSize, roadWidthE / 2);
      ctx.moveTo(eS1X, eS1Y);
      ctx.lineTo(eS2X, eS2Y);
      ctx.stroke();

      // West Stop Line (incoming lanes: Y < 0, at X = -halfSize)
      ctx.beginPath();
      const [wS1X, wS1Y] = worldToCanvas(-halfSize, -roadWidthW / 2);
      const [wS2X, wS2Y] = worldToCanvas(-halfSize, 0);
      ctx.moveTo(wS1X, wS1Y);
      ctx.lineTo(wS2X, wS2Y);
      ctx.stroke();
    }

    // 5. Draw Crosswalks
    if (showCrosswalks) {
      ctx.fillStyle = 'rgba(255, 255, 255, 0.25)';
      const stripeW = 1.0;
      const stripeS = 2.0;

      // Draw crosswalk stripes for an approach
      const drawCrosswalkApproach = (dir: 'N' | 'S' | 'E' | 'W', widthRoad: number) => {
        const cwDist = halfSize + 3.0; // distance from center
        const stripesCount = Math.floor(widthRoad / stripeS);
        for (let i = 0; i < stripesCount; i++) {
          const offset = -widthRoad / 2 + i * stripeS + stripeS / 2;
          if (dir === 'N' || dir === 'S') {
            const yCoord = dir === 'N' ? cwDist : -cwDist;
            const [cX, cY] = worldToCanvas(offset, yCoord);
            ctx.fillRect(cX - stripeW / 2, cY - (2 * ppm) / 2, stripeW * ppm, 2 * ppm);
          } else {
            const xCoord = dir === 'E' ? cwDist : -cwDist;
            const [cX, cY] = worldToCanvas(xCoord, offset);
            ctx.fillRect(cX - (2 * ppm) / 2, cY - stripeW / 2, 2 * ppm, stripeW * ppm);
          }
        }
      };

      drawCrosswalkApproach('N', roadWidthN);
      drawCrosswalkApproach('S', roadWidthS);
      drawCrosswalkApproach('E', roadWidthE);
      drawCrosswalkApproach('W', roadWidthW);
    }

    // 6. Draw Vehicles
    vehicles.forEach((veh) => {
      const [vX, vY] = worldToCanvas(veh.x, veh.y);
      const length = 4.5; // meters
      const widthVeh = 2.0; // meters

      const lengthPx = length * ppm;
      const widthPx = widthVeh * ppm;

      ctx.save();
      ctx.translate(vX, vY);
      ctx.rotate((veh.heading * Math.PI) / 180);

      // Color coding: waiting (speed < 0.3) -> red/coral; yielding (approaching/slow) -> yellow; moving -> teal
      let fillStyle = '#2a9d8f'; // moving (teal)
      if (veh.state === 'waiting' || veh.speed < 0.3) {
        fillStyle = '#e63946'; // waiting (coral/red)
      } else if (veh.state === 'approaching' && veh.speed < 2.0) {
        fillStyle = '#ffb703'; // yielding (yellow/orange)
      }

      ctx.fillStyle = fillStyle;
      ctx.fillRect(-widthPx / 2, -lengthPx / 2, widthPx, lengthPx);

      // Outline
      ctx.strokeStyle = '#1d3557';
      ctx.lineWidth = 1;
      ctx.strokeRect(-widthPx / 2, -lengthPx / 2, widthPx, lengthPx);

      // Front directional triangle
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.moveTo(0, -lengthPx / 2 - 2);
      ctx.lineTo(-3, -lengthPx / 2 + 3);
      ctx.lineTo(3, -lengthPx / 2 + 3);
      ctx.closePath();
      ctx.fill();

      ctx.restore();
    });

    // 7. Draw Lane Queue Debug Indicators
    if (debug) {
      // Helper to count vehicles near approaches
      const getQueueCount = (dir: 'N' | 'S' | 'E' | 'W') => {
        return vehicles.filter((veh) => {
          const lane = veh.lane_id.toUpperCase();
          const inDir = lane.startsWith(dir);
          const isSlow = veh.speed < 0.5;
          return inDir && isSlow;
        }).length;
      };

      const directions: ('N' | 'S' | 'E' | 'W')[] = ['N', 'S', 'E', 'W'];
      directions.forEach((dir) => {
        const count = getQueueCount(dir);
        let badgeX = 0;
        let badgeY = 0;

        // Position badge near stop line of the approach
        switch (dir) {
          case 'N':
            [badgeX, badgeY] = worldToCanvas(-roadWidthN / 2 - 4.0, halfSize + 2.0);
            break;
          case 'S':
            [badgeX, badgeY] = worldToCanvas(roadWidthS / 2 + 4.0, -halfSize - 2.0);
            break;
          case 'E':
            [badgeX, badgeY] = worldToCanvas(halfSize + 2.0, roadWidthE / 2 + 4.0);
            break;
          case 'W':
            [badgeX, badgeY] = worldToCanvas(-halfSize - 2.0, -roadWidthW / 2 - 4.0);
            break;
        }

        // Draw badge box
        ctx.fillStyle = 'rgba(230, 57, 70, 0.9)';
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        const badgeW = 45;
        const badgeH = 20;
        ctx.fillRect(badgeX - badgeW / 2, badgeY - badgeH / 2, badgeW, badgeH);
        ctx.strokeRect(badgeX - badgeW / 2, badgeY - badgeH / 2, badgeW, badgeH);

        // Draw text
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`Q: ${count.toString()}`, badgeX, badgeY);
      });
    }

    // 8. General Overlay (Status & Clock)
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.fillRect(10, 10, 200, 50);

    ctx.fillStyle = '#ffffff';
    ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`Simulation: ${status.toUpperCase()}`, 20, 28);
    const activeCount = vehicles.length;
    ctx.fillText(`Active Vehicles: ${activeCount.toString()}`, 20, 44);

  }, [
    vehicles,
    status,
    width,
    height,
    lanesNorth,
    lanesSouth,
    lanesEast,
    lanesWest,
    laneWidth,
    intersectionSize,
    showCrosswalks,
    showStopLines,
    debug,
    ppm,
  ]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{
        border: '1px solid #1a1a1a',
        borderRadius: '8px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        display: 'block',
      }}
    />
  );
};
