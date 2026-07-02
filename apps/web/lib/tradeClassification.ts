export type TradeResult = "WIN" | "LOSS" | "BREAKEVEN" | "OPEN" | "-";

export const TRADE_R_EPSILON = 0.01;

export function numberFromTradeValue(value: unknown): number {
  const n = Number(String(value ?? "").replace(/[R,$,% ]/g, ""));
  return Number.isFinite(n) ? n : NaN;
}

export function classifyTradeResultFromR(value: unknown): TradeResult {
  const r = numberFromTradeValue(value);
  if (!Number.isFinite(r)) return "-";
  if (r > TRADE_R_EPSILON) return "WIN";
  if (r < -TRADE_R_EPSILON) return "LOSS";
  return "BREAKEVEN";
}

export function classifyTradeRow(row: Record<string, any>): TradeResult {
  const status = String(row.status || "").toUpperCase();
  if (status === "OPEN") return "OPEN";

  const rResult = classifyTradeResultFromR(row.r_multiple ?? row.R_multiple ?? row.r);
  if (rResult !== "-") return rResult;

  const explicit = String(row.result || "").toUpperCase();
  if (["WIN", "LOSS", "BREAKEVEN", "OPEN"].includes(explicit)) return explicit as TradeResult;

  const entry = Number(row.entry_price ?? row.entry);
  const exit = Number(row.exit_price ?? row.exit);
  if (Number.isFinite(entry) && Number.isFinite(exit)) {
    const side = String(row.side || "BUY").toUpperCase();
    const pnl = side === "SELL" ? entry - exit : exit - entry;
    if (pnl > 0) return "WIN";
    if (pnl < 0) return "LOSS";
    return "BREAKEVEN";
  }

  return "-";
}

export function cleanupExitReason(reason: unknown, rValue: unknown): string {
  const normalized = String(reason || "")
    .trim()
    .toUpperCase()
    .replace(/\s+/g, "_");
  const result = classifyTradeResultFromR(rValue);
  if (result === "WIN" && ["TARGET1", "TARGET_1", "TARGET1_HIT", "TARGET2", "TARGET_2", "TARGET2_HIT"].includes(normalized)) {
    return normalized;
  }
  if (result === "LOSS" && ["STOP", "STOP_LOSS", "STOP_HIT"].includes(normalized)) {
    return normalized;
  }
  if (result === "WIN") return "POSITIVE_EXIT";
  if (result === "LOSS") return "NEGATIVE_EXIT";
  if (result === "BREAKEVEN") return "BREAKEVEN_EXIT";
  return normalized;
}
