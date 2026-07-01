'use client';

import {useEffect, useRef} from 'react';

export type TradingCandle = { time: string | number; open: number; high: number; low: number; close: number; volume?: number };
export type TradingMarker = { time: string | number; position?: 'aboveBar' | 'belowBar'; color?: string; shape?: 'arrowUp' | 'arrowDown' | 'circle'; text?: string; price?: number };
export type TradingLine = { title: string; price: number; color?: string; style?: 'solid' | 'dashed' };

export default function TradingChart({
  candles,
  markers = [],
  lines = [],
  height = 320,
}: {
  candles: TradingCandle[];
  markers?: TradingMarker[];
  lines?: TradingLine[];
  height?: number;
}) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, width, h);
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, width, h);
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let y = 30; y < h - 20; y += 45) {
      ctx.beginPath(); ctx.moveTo(42, y); ctx.lineTo(width - 14, y); ctx.stroke();
    }
    const data = candles.length ? candles : [
      {time: 1, open: 100, high: 102, low: 99, close: 101},
      {time: 2, open: 101, high: 103, low: 100, close: 102},
      {time: 3, open: 102, high: 104, low: 98, close: 99},
      {time: 4, open: 99, high: 105, low: 98, close: 104},
      {time: 5, open: 104, high: 106, low: 103, close: 105},
    ];
    const prices = data.flatMap(c => [c.open, c.high, c.low, c.close]).concat(lines.map(l => l.price), markers.map(m => m.price || 0).filter(Boolean));
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const pad = Math.max(1e-9, (max - min) * 0.08);
    const yOf = (p: number) => h - 28 - ((p - min + pad) / (max - min + pad * 2)) * (h - 55);
    const xStep = (width - 70) / Math.max(1, data.length);
    data.forEach((c, i) => {
      const x = 48 + i * xStep + xStep / 2;
      const up = c.close >= c.open;
      ctx.strokeStyle = up ? '#22c55e' : '#ef4444';
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath(); ctx.moveTo(x, yOf(c.high)); ctx.lineTo(x, yOf(c.low)); ctx.stroke();
      const top = yOf(Math.max(c.open, c.close));
      const bottom = yOf(Math.min(c.open, c.close));
      ctx.fillRect(x - Math.max(2, xStep * 0.28), top, Math.max(4, xStep * 0.56), Math.max(2, bottom - top));
    });
    lines.forEach(line => {
      const y = yOf(line.price);
      ctx.strokeStyle = line.color || '#38bdf8';
      ctx.setLineDash(line.style === 'dashed' ? [6, 4] : []);
      ctx.beginPath(); ctx.moveTo(42, y); ctx.lineTo(width - 14, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = line.color || '#38bdf8';
      ctx.fillText(`${line.title} ${line.price}`, 48, y - 4);
    });
    markers.forEach(marker => {
      const idx = Math.max(0, data.findIndex(c => String(c.time) === String(marker.time)));
      const candle = data[idx] || data[data.length - 1];
      const x = 48 + idx * xStep + xStep / 2;
      const y = marker.price ? yOf(marker.price) : marker.position === 'aboveBar' ? yOf(candle.high) - 12 : yOf(candle.low) + 12;
      ctx.fillStyle = marker.color || (marker.position === 'aboveBar' ? '#ef4444' : '#22c55e');
      ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
      if (marker.text) ctx.fillText(marker.text, x + 7, y + 4);
    });
    ctx.fillStyle = '#94a3b8';
    ctx.fillText('QuantOS chart: own local-engine/CSV/backtest data only', 48, 18);
  }, [candles, markers, lines]);

  return <canvas ref={ref} width={900} height={height} style={{width:'100%', height, background:'#0f172a', borderRadius:12, border:'1px solid #1e293b'}} aria-label="Trading chart" />;
}
