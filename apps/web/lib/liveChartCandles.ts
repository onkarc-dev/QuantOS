export type LiveChartCandle = {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

export function visibleChartCandle(candle: LiveChartCandle): LiveChartCandle {
  const close = Number(candle.close);
  const sourceOpen = Number(candle.open);
  const sourceHigh = Number(candle.high);
  const sourceLow = Number(candle.low);
  const base = Math.max(Math.abs(close), Math.abs(sourceOpen), 1);
  const minBody = base * 0.000001;
  const minWick = base * 0.000002;

  let open = sourceOpen;
  if (Math.abs(close - open) < minBody) {
    open = close >= open ? close - minBody : close + minBody;
  }

  const high = Math.max(sourceHigh, open, close);
  const low = Math.min(sourceLow, open, close);
  const mid = (high + low) / 2;
  const visibleHigh = high - low < minWick ? mid + minWick / 2 : high;
  const visibleLow = high - low < minWick ? mid - minWick / 2 : low;

  return {
    ...candle,
    open,
    high: Math.max(visibleHigh, open, close),
    low: Math.min(visibleLow, open, close),
    close,
  };
}

export function normalizeLiveCandle(raw: any): LiveChartCandle | null {
  const open = Number(raw?.open);
  const high = Number(raw?.high);
  const low = Number(raw?.low);
  const close = Number(raw?.close);
  const time = raw?.time ?? raw?.timestamp ?? raw?.ts;
  if (!time || !Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
    return null;
  }
  if (open <= 0 || high <= 0 || low <= 0 || close <= 0) return null;
  const normalizedHigh = Math.max(open, high, low, close);
  const normalizedLow = Math.min(open, high, low, close);
  return {
    time,
    open,
    high: normalizedHigh,
    low: normalizedLow,
    close,
    volume: Number.isFinite(Number(raw?.volume)) ? Number(raw.volume) : undefined,
  };
}

export function normalizeLiveCandles(raw: any): LiveChartCandle[] {
  if (!Array.isArray(raw)) return [];
  return raw.map(normalizeLiveCandle).filter(Boolean).slice(-1000) as LiveChartCandle[];
}

export function candlesForSymbol(candlesBySymbol: any, symbol: string): LiveChartCandle[] {
  if (!candlesBySymbol || typeof candlesBySymbol !== "object") return [];
  const wanted = String(symbol || "").toUpperCase();
  const key = Object.keys(candlesBySymbol).find((candidate) => candidate.toUpperCase() === wanted);
  return normalizeLiveCandles(key ? candlesBySymbol[key] : []);
}

export function appendTelemetryCandle(
  existing: LiveChartCandle[],
  priceValue: unknown,
  timestampValue: unknown,
  barSecondsValue: unknown,
  maxCandles = 1000,
): LiveChartCandle[] {
  const price = Number(priceValue);
  if (!Number.isFinite(price) || price <= 0) return existing.slice(-maxCandles);

  const barSeconds = Math.max(1, Number(barSecondsValue) || 1);
  const parsedTs =
    typeof timestampValue === "number"
      ? timestampValue
      : timestampValue
        ? Date.parse(String(timestampValue))
        : Date.now();
  const tsMs = Number.isFinite(parsedTs) ? parsedTs : Date.now();
  const bucketSeconds = Math.floor(tsMs / 1000 / barSeconds) * barSeconds;
  const next = existing.slice(-maxCandles);
  const last = next[next.length - 1];

  if (last && Number(last.time) === bucketSeconds) {
    next[next.length - 1] = {
      ...last,
      high: Math.max(last.high, price),
      low: Math.min(last.low, price),
      close: price,
    };
  } else {
    const open = Number.isFinite(Number(last?.close)) ? Number(last?.close) : price;
    next.push({
      time: bucketSeconds,
      open,
      high: Math.max(open, price),
      low: Math.min(open, price),
      close: price,
    });
  }

  return next.slice(-maxCandles);
}
