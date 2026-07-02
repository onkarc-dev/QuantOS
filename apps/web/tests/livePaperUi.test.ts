import assert from "node:assert/strict";
import test from "node:test";

import { appendTelemetryCandle, normalizeLiveCandle, visibleChartCandle } from "../lib/liveChartCandles.ts";
import { classifyTradeRow, cleanupExitReason } from "../lib/tradeClassification.ts";

test("classifies trade rows from R before stale explicit result", () => {
  assert.equal(classifyTradeRow({ result: "LOSS", r: 0.193 }), "WIN");
  assert.equal(classifyTradeRow({ result: "WIN", r: -1.015 }), "LOSS");
  assert.equal(classifyTradeRow({ result: "LOSS", r: 0.0 }), "BREAKEVEN");
  assert.equal(classifyTradeRow({ status: "OPEN", r: 0.303 }), "OPEN");
});

test("cleans non-target exit reasons from R", () => {
  assert.equal(cleanupExitReason("NEGATIVE_EXIT", 0.303), "POSITIVE_EXIT");
  assert.equal(cleanupExitReason("TIME_EXIT", -0.303), "NEGATIVE_EXIT");
  assert.equal(cleanupExitReason("FORCED_EXIT", 0.0), "BREAKEVEN_EXIT");
});

test("normalizes and appends valid OHLC live chart candles", () => {
  const normalized = normalizeLiveCandle({ time: 1700000000, open: 100, high: 99, low: 101, close: 100.5 });
  assert.deepEqual(normalized && { open: normalized.open, high: normalized.high, low: normalized.low, close: normalized.close }, {
    open: 100,
    high: 101,
    low: 99,
    close: 100.5,
  });

  const candles = appendTelemetryCandle([{ time: 1700000000, open: 100, high: 101, low: 99, close: 100.5 }], 101.25, 1700000001000, 1, 1000);
  assert.equal(candles.at(-1)?.open, 100.5);
  assert.equal(candles.at(-1)?.close, 101.25);
  assert.ok((candles.at(-1)?.high ?? 0) >= 101.25);
  assert.ok((candles.at(-1)?.low ?? 0) <= 100.5);
});

test("expands flat 1s candles into visible candlestick bodies and wicks", () => {
  const visual = visibleChartCandle({ time: 1700000000, open: 50000, high: 50000, low: 50000, close: 50000 });
  assert.ok(visual.close >= visual.open);
  assert.ok(visual.high > visual.low);
  assert.ok(visual.close > visual.open);
});
