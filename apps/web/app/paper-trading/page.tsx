"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { api, formatApiError } from "../../lib/api";

type StrategyRow = {
  id: string;
  name?: string;
  timeframe?: string;
  symbols?: string[];
  config?: any;
  user_strategy_id?: string;
};

type LiveStatus = {
  status: string;
  session_id?: string;
  selected_strategy_id?: string;
  selected_strategy_name?: string;
  live_config?: any;
  last_price?: number;
  processed?: number;
  realized_pnl?: number;
  unrealized_pnl?: number;
  events?: any[];
  stdout_tail?: string[];
  error?: string;
  metrics?: Record<string, any>;
  session_metrics?: Record<string, any>;
  markets?: any[];
  supported_markets?: any[];
  symbol_states?: Record<string, any>;
  engine?: Record<string, any>;
  wallet?: {
    starting_balance: number;
    current_balance: number;
    account_equity?: number;
    cash_balance?: number;
    realized_pnl: number;
    unrealized_pnl: number;
    locked_until?: string;
  };
};

const SUPPORTED_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "BNBUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "ADAUSDT",
  "DOGEUSDT",
  "AVAXUSDT",
  "LINKUSDT",
  "TRXUSDT",
];

function money(v: unknown) {
  const n = typeof v === "number" ? v : Number(v || 0);
  return Number.isFinite(n) ? n.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "-";
}

function num(v: any, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function cleanTime(v: any) {
  if (!v) return "-";
  const d = new Date(String(v).replace("+00:00Z", "Z"));
  if (Number.isNaN(d.getTime())) return String(v).replace("T", " ").replace("Z", " UTC");
  return d.toLocaleString(undefined, { hour12: false });
}

function signedStyle(value: any): CSSProperties {
  const n = Number(String(value ?? "").replace(/[$,%Rμs, ]/g, ""));
  if (!Number.isFinite(n)) return {};
  if (n > 0) return { color: "#22c55e", fontWeight: 800 };
  if (n < 0) return { color: "#ef4444", fontWeight: 800 };
  return { color: "#e5e7eb" };
}

function buildMarketRows(status: LiveStatus, selectedSymbols: string[]) {
  const fromApi = Array.isArray(status.markets)
    ? status.markets
    : Array.isArray(status.supported_markets)
      ? status.supported_markets
      : [];

  const states = status.symbol_states || {};
  const activeSymbols = new Set(
    Object.keys(states).length
      ? Object.keys(states).map((x) => x.toUpperCase())
      : status.status === "running" || status.status === "starting"
        ? selectedSymbols.map((x) => x.toUpperCase())
        : [],
  );

  return SUPPORTED_SYMBOLS.map((sym) => {
    const apiRow = fromApi.find((m: any) => String(m.symbol || "").toUpperCase() === sym) || {};
    const st = states[sym] || {};
    const isActive = activeSymbols.has(sym) && (status.status === "running" || status.status === "starting");
    return {
      symbol: sym,
      covered: apiRow.covered ?? true,
      paper_status: isActive ? "ACTIVE_WEBSOCKET" : apiRow.paper_status || "SUPPORTED",
      latest_price: st.last_price || apiRow.latest_price || (sym === status.live_config?.symbols?.[0] ? status.last_price : 0),
      messages: st.processed ?? apiRow.messages ?? (isActive ? status.processed || 0 : 0),
      bars: st.bars ?? apiRow.bars ?? 0,
      signals: st.signals ?? apiRow.signals ?? 0,
      trades: st.total_trades ?? apiRow.trades ?? 0,
      p95_engine_us: st.p95_engine_us ?? apiRow.p95_engine_us ?? 0,
    };
  });
}

function buildTradeRows(events: any[]) {
  const rows: any[] = [];
  const openBySymbol: Record<string, any[]> = {};
  for (const e of [...(events || [])].reverse()) {
    const type = String(e.event_type || "");
    const symbol = String(e.symbol || "BTCUSDT").toUpperCase();
    openBySymbol[symbol] = openBySymbol[symbol] || [];
    if (type === "PAPER_BUY_FILL") {
      openBySymbol[symbol].push({
        symbol,
        side: "BUY",
        entry_time: e.created_at,
        entry_price: e.fill || e.entry || e.price,
        qty: e.qty || "-",
        status: "OPEN",
        result: "OPEN",
        stop: e.stop,
        target1: e.target1,
        target2: e.target2,
      });
    }
    if (type === "PAPER_SELL_FILL") {
      const buy = openBySymbol[symbol]?.pop();
      const entry = num(e.entry || buy?.entry_price, NaN);
      const exit = num(e.exit || e.fill || e.price, NaN);
      const pnl = Number.isFinite(entry) && Number.isFinite(exit) ? exit - entry : num(e.pnl, 0);
      rows.push({
        symbol,
        side: "BUY",
        entry_time: buy?.entry_time || e.entry_time || e.created_at,
        entry_price: entry,
        qty: e.qty || buy?.qty || "-",
        exit_time: e.created_at,
        exit_price: exit,
        exit_reason: String(e.exit_reason || e.reason || "CLOSED").replaceAll("_", " "),
        result: pnl > 0 ? "WIN" : pnl < 0 ? "LOSS" : "BREAKEVEN",
        r: e.R_multiple || e.r || "-",
        pnl: e.pnl || pnl,
        stop: e.stop || buy?.stop,
        target1: e.target1 || buy?.target1,
        target2: e.target2 || buy?.target2,
        status: "CLOSED",
      });
    }
  }
  const openRows = Object.values(openBySymbol).flat();
  return [...openRows, ...rows].reverse();
}

function buildOpenPositions(status: LiveStatus, tradeRows: any[]) {
  const states = status.symbol_states || {};
  const byState = Object.entries(states)
    .filter(([, st]: any) => num(st?.open_trade || st?.open_positions, 0) > 0)
    .map(([symbol, st]: any) => ({
      symbol,
      side: st.open_side || "BUY",
      entry_price: st.open_entry,
      qty: st.open_qty || st.qty || "-",
      current_price: st.last_price,
      current_R: st.current_R,
      unrealized_pnl: st.unrealized_pnl,
      stop: st.open_stop,
      target1: st.target1,
      target2: st.target2,
    }));
  return byState.length ? byState : tradeRows.filter((t) => t.status === "OPEN");
}

export default function PaperTradingPage() {
  const [status, setStatus] = useState<LiveStatus>({ status: "loading" });
  const [strategies, setStrategies] = useState<StrategyRow[]>([]);
  const [selectedStrategyId, setSelectedStrategyId] = useState("");
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>(["BTCUSDT"]);
  const [message, setMessage] = useState("Live paper trading uses the C++ Binance WebSocket paper engine. No real-money execution.");
  const [busy, setBusy] = useState(false);
  const loadingRef = useRef(false);

  async function refresh() {
    if (loadingRef.current) return;
    loadingRef.current = true;
    try {
      const next = (await api("/live-paper/status")) as LiveStatus;
      setStatus(next);
    } catch (err) {
      const m = formatApiError(err);
      setMessage(m);
      setStatus({ status: "error", error: m });
    } finally {
      loadingRef.current = false;
    }
  }

  async function loadStrategies() {
    try {
      const rows: any = await api("/strategies");
      const list = Array.isArray(rows) ? rows : [];
      setStrategies(list);
      if (!selectedStrategyId && list.length) {
        setSelectedStrategyId(list[0].id);
        setSelectedSymbols(list[0].symbols?.length ? list[0].symbols : ["BTCUSDT"]);
      }
    } catch (err) {
      setMessage(`Could not load Strategy Builder configs: ${formatApiError(err)}`);
    }
  }

  async function start() {
    setBusy(true);
    try {
      const r = (await api("/live-paper/start", {
        method: "POST",
        body: JSON.stringify({ strategy_id: selectedStrategyId || undefined, symbols: selectedSymbols }),
      })) as LiveStatus;
      setStatus(r);
      setMessage(
        r.status === "disabled"
          ? r.error || "Live paper engine is disabled. Check /system/engine-diagnostics."
          : `Live paper session started on ${selectedSymbols.join(", ")}. Waiting for live Binance WebSocket ticks.`,
      );
    } catch (err) {
      setMessage(formatApiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    setBusy(true);
    try {
      setStatus((await api("/live-paper/stop", { method: "POST" })) as LiveStatus);
      setMessage("Session stopped. Final live paper report generated.");
    } catch (err) {
      setMessage(formatApiError(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadStrategies();
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const active = status.status === "running" || status.status === "starting";
    const id = setInterval(refresh, active ? 1500 : 5000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.status]);

  const metrics = status.session_metrics || status.metrics || {};
  const liveConfig = status.live_config || {};
  const wallet = status.wallet || { starting_balance: 100000, current_balance: 100000, realized_pnl: 0, unrealized_pnl: 0 };
  const realizedPnl = status.realized_pnl ?? wallet.realized_pnl ?? 0;
  const unrealizedPnl = status.unrealized_pnl ?? wallet.unrealized_pnl ?? 0;
  const cashBalance = wallet.cash_balance ?? wallet.starting_balance + realizedPnl;
  const accountEquity = wallet.account_equity ?? wallet.current_balance ?? cashBalance + unrealizedPnl;
  const tradeRows = useMemo(() => buildTradeRows(status.events || []), [status.events]);
  const openPositions = useMemo(() => buildOpenPositions(status, tradeRows), [status.symbol_states, tradeRows]);
  const marketRows = useMemo(() => buildMarketRows(status, selectedSymbols), [status, selectedSymbols]);
  const activeMarkets = marketRows.filter((m) => m.paper_status === "ACTIVE_WEBSOCKET");
  const primaryMarket = activeMarkets[0] || marketRows.find((m) => m.symbol === selectedSymbols[0]);
  const selectedStrategy = strategies.find((s) => s.id === selectedStrategyId);
  const selectedConfig = selectedStrategy?.config || {};
  const selectedRules = selectedConfig.strategy || selectedConfig || {};
  const selectedRisk = selectedRules.risk || selectedConfig.risk || {};
  const selectedTargets = selectedRules.targets || selectedConfig.targets || {};
  const activeStrategyName = status.selected_strategy_name || liveConfig.name || selectedStrategy?.name || selectedRules.name || "QuantOS Strategy";
  const activeStrategyId = status.selected_strategy_id || liveConfig.strategy_id || selectedStrategy?.user_strategy_id || selectedConfig.user_strategy_id || selectedStrategyId || "-";
  const cfgLookback = metrics.cfg_lookback ?? liveConfig.strategy?.breakout_lookback ?? selectedRules.breakout_lookback ?? "-";
  const cfgMinScore = metrics.cfg_min_score ?? liveConfig.strategy?.min_setup_score ?? selectedRules.min_setup_score ?? "-";
  const cfgRiskPct = metrics.cfg_risk_pct ?? liveConfig.strategy?.risk?.risk_per_trade_pct ?? selectedRisk.risk_per_trade_pct ?? "-";
  const cfgTarget1 = liveConfig.strategy?.targets?.target1_R ?? selectedTargets.target1_R ?? "-";
  const cfgTarget2 = liveConfig.strategy?.targets?.target2_R ?? selectedTargets.target2_R ?? "-";
  const activeBarSeconds = metrics.cfg_bar_seconds || liveConfig.bar_seconds || selectedConfig.bar_seconds || "-";
  const canStart = !busy && status.status !== "running" && status.status !== "starting" && !wallet.locked_until;
  const canStop = !busy && (status.status === "running" || status.status === "starting");
  const isLive = status.status === "running" || status.status === "starting";

  function toggleLiveSymbol(sym: string) {
    const set = new Set(selectedSymbols);
    set.has(sym) ? set.delete(sym) : set.add(sym);
    const next = [...set];
    setSelectedSymbols(next.length ? next : ["BTCUSDT"]);
  }

  return (
    <main style={{ padding: 24, maxWidth: 1280, margin: "0 auto" }}>
      <section style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 34, marginBottom: 8 }}>Live Paper Trading</h1>
        <p style={{ color: "#94a3b8" }}>10 Binance USDT markets · real WebSocket data · C++ paper broker · no real broker orders.</p>
      </section>

      <section style={panelStyle}>
        <h2 style={h2Style}>Live Strategy Builder Config</h2>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(260px,1fr) repeat(5,minmax(120px,170px))", gap: 12, alignItems: "end" }}>
          <label style={{ display: "grid", gap: 6, color: "#94a3b8", fontSize: 13 }}>
            Strategy used by live C++ engine
            <select value={selectedStrategyId} onChange={(e) => setSelectedStrategyId(e.target.value)} disabled={!canStart} style={inputStyle}>
              <option value="">Latest saved strategy / default config</option>
              {strategies.map((s) => <option key={s.id} value={s.id}>{s.name || "Strategy"} · {s.user_strategy_id || s.id.slice(0, 8)}</option>)}
            </select>
          </label>
          <Mini label="Active" value={activeStrategyName} />
          <Mini label="Lookback" value={String(cfgLookback)} />
          <Mini label="Min score" value={String(cfgMinScore)} />
          <Mini label="Risk %" value={String(cfgRiskPct)} />
          <Mini label="Bar length" value={activeBarSeconds === "-" ? "-" : `${activeBarSeconds}s`} />
        </div>
        <div style={{ marginTop: 14, borderTop: "1px solid #243044", paddingTop: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <b>Activate paper markets</b>
            <div><button type="button" onClick={() => setSelectedSymbols([...SUPPORTED_SYMBOLS])} disabled={!canStart}>Select all</button>{" "}<button type="button" className="secondary" onClick={() => setSelectedSymbols(selectedStrategy?.symbols?.length ? selectedStrategy.symbols : ["BTCUSDT"])} disabled={!canStart}>Use strategy symbols</button></div>
          </div>
          <div className="symbol-picker">{SUPPORTED_SYMBOLS.map((sym) => <label key={sym} className="symbol-chip"><input type="checkbox" checked={selectedSymbols.includes(sym)} disabled={!canStart} onChange={() => toggleLiveSymbol(sym)} /><span>{sym}</span></label>)}</div>
          <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 8 }}>Selected active markets: {selectedSymbols.join(", ")}.</p>
        </div>
      </section>

      <section style={{ display: "flex", gap: 12, flexWrap: "wrap", margin: "20px 0" }}>
        <button onClick={start} disabled={!canStart}>Start Live Paper Trading</button>
        <button onClick={stop} disabled={!canStop} style={{ background: "#ef4444" }}>Stop & Exit</button>
        <button onClick={() => { loadStrategies(); refresh(); }} disabled={busy} className="secondary">Refresh</button>
        <span style={{ padding: "10px 14px", border: `1px solid ${isLive ? "#22c55e" : "#475569"}`, borderRadius: 8, color: isLive ? "#86efac" : "#cbd5e1", fontWeight: 800 }}>{isLive ? "🟢 LIVE" : "⚪ IDLE"}</span>
      </section>

      <p style={{ marginBottom: 20, color: status.error ? "#fecaca" : "#cbd5e1" }}>{message}</p>
      {status.error && <pre style={{ whiteSpace: "pre-wrap", background: "#1e1b4b", padding: 12, borderRadius: 8, marginBottom: 20 }}>{status.error}</pre>}

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: 14, marginBottom: 20 }}>
        <Card label="Live status" value={isLive ? "TRADING" : "STOPPED"} accent={isLive ? "#22c55e" : undefined} />
        <Card label={`${primaryMarket?.symbol || selectedSymbols[0]} price`} value={primaryMarket?.latest_price ? `$${money(primaryMarket.latest_price)}` : "waiting"} />
        <Card label="Account equity" value={`$${money(accountEquity)}`} />
        <Card label="Cash balance" value={`$${money(cashBalance)}`} />
        <Card label="Realized PnL" value={`$${money(realizedPnl)}`} signed />
        <Card label="Unrealized PnL" value={`$${money(unrealizedPnl)}`} signed />
        <Card label="Active markets" value={`${activeMarkets.length}/${SUPPORTED_SYMBOLS.length}`} accent="#38bdf8" />
        <Card label="Ticks processed" value={String(status.processed || metrics.processed || 0)} />
        <Card label="Bars" value={String(metrics.bars || 0)} />
        <Card label="Signals" value={String(metrics.signals || 0)} />
        <Card label="Total trades" value={String(metrics.total_trades || 0)} />
        <Card label="P95 engine" value={metrics.p95_engine_us ? `${metrics.p95_engine_us} μs` : "-"} />
        <Card label="Strategy ID" value={activeStrategyId} />
        <Card label="Live bar length" value={activeBarSeconds === "-" ? "-" : `${activeBarSeconds}s`} />
      </section>

      <section style={panelStyle}>
        <h2 style={h2Style}>10 Binance Markets Monitor</h2>
        <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 10 }}>Rows marked ACTIVE_WEBSOCKET are running with their own C++ Binance WebSocket stream.</p>
        <div style={{ overflowX: "auto" }}>
          <table className="pro-table" style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead><tr><Th>Symbol</Th><Th>Covered</Th><Th>Status</Th><Th>Latest price</Th><Th>Messages</Th><Th>Bars</Th><Th>Signals</Th><Th>Trades</Th><Th>P95 engine</Th></tr></thead>
            <tbody>{marketRows.map((m) => <tr key={m.symbol}><Td>{m.symbol}</Td><Td>{m.covered ? "YES" : "NO"}</Td><Td><span className={m.paper_status === "ACTIVE_WEBSOCKET" ? "pill pill-green" : "pill pill-white"}>{m.paper_status}</span></Td><Td>{m.latest_price ? `$${money(m.latest_price)}` : "-"}</Td><Td>{m.messages || 0}</Td><Td>{m.bars || 0}</Td><Td>{m.signals || 0}</Td><Td>{m.trades || 0}</Td><Td>{m.p95_engine_us ? `${m.p95_engine_us} μs` : "-"}</Td></tr>)}</tbody>
          </table>
        </div>
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(420px,1fr))", gap: 16, marginTop: 20 }}>
        <div style={panelStyle}><h2 style={h2Style}>Open Positions</h2>{openPositions.length ? <SimplePositions rows={openPositions} /> : <Empty text="No open positions right now. New positions will appear here with symbol, entry, stop, targets and live R." />}</div>
        <div style={panelStyle}><h2 style={h2Style}>Live Strategy Config</h2><table style={{ width: "100%", borderCollapse: "collapse" }}><tbody><SummaryRow label="Strategy ID" value={activeStrategyId} /><SummaryRow label="Strategy name" value={activeStrategyName} /><SummaryRow label="Symbols" value={(liveConfig.symbols || selectedSymbols).join(", ")} /><SummaryRow label="Timeframe" value={liveConfig.timeframe || "15s"} /><SummaryRow label="Lookback / Min score" value={`${cfgLookback} / ${cfgMinScore}`} /><SummaryRow label="Risk / Targets" value={`${cfgRiskPct}% · ${cfgTarget1}R / ${cfgTarget2}R`} /></tbody></table></div>
      </section>

      <section style={{ ...panelStyle, marginTop: 16 }}><h2 style={h2Style}>Trade Journal</h2>{tradeRows.length ? <TradeTable rows={tradeRows} /> : <Empty text="No paper trades yet. The strategy needs enough closed bars and a valid setup before it opens a trade." />}</section>
    </main>
  );
}

function Card({ label, value, signed, accent }: { label: string; value: string; signed?: boolean; accent?: string }) {
  return <div style={cardStyle}><div style={{ color: "#94a3b8", fontSize: 12 }}>{label}</div><div style={{ fontSize: 24, fontWeight: 900, marginTop: 6, color: accent, ...(signed ? signedStyle(value) : {}) }}>{value}</div></div>;
}
function Mini({ label, value }: { label: string; value: string }) { return <div style={miniStyle}><div style={{ color: "#94a3b8", fontSize: 11 }}>{label}</div><b>{value}</b></div>; }
function Th({ children }: { children: React.ReactNode }) { return <th style={{ textAlign: "left", padding: "10px 8px", color: "#94a3b8", borderBottom: "1px solid #334155" }}>{children}</th>; }
function Td({ children }: { children: React.ReactNode }) { return <td style={{ padding: "9px 8px", borderBottom: "1px solid #1e293b" }}>{children}</td>; }
function SummaryRow({ label, value }: { label: string; value: string }) { return <tr><Td><b>{label}</b></Td><Td>{value}</Td></tr>; }
function Empty({ text }: { text: string }) { return <div style={{ border: "1px dashed #334155", borderRadius: 10, padding: 16, color: "#94a3b8" }}>{text}</div>; }
function SimplePositions({ rows }: { rows: any[] }) { return <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><Th>Symbol</Th><Th>Side</Th><Th>Entry</Th><Th>Current</Th><Th>Unrealized</Th></tr></thead><tbody>{rows.map((p, i) => <tr key={`${p.symbol}-${i}`}><Td>{p.symbol}</Td><Td>{p.side || "BUY"}</Td><Td>{p.entry_price ? `$${money(p.entry_price)}` : "-"}</Td><Td>{p.current_price ? `$${money(p.current_price)}` : "-"}</Td><Td><span style={signedStyle(p.unrealized_pnl)}>{p.unrealized_pnl !== undefined ? `$${money(p.unrealized_pnl)}` : "-"}</span></Td></tr>)}</tbody></table></div>; }
function TradeTable({ rows }: { rows: any[] }) { return <div style={{ overflowX: "auto" }}><table style={{ width: "100%", borderCollapse: "collapse" }}><thead><tr><Th>#</Th><Th>Symbol</Th><Th>Side</Th><Th>Entry time</Th><Th>Entry</Th><Th>Exit time</Th><Th>Exit</Th><Th>Reason</Th><Th>Result</Th><Th>R</Th></tr></thead><tbody>{rows.map((t, i) => <tr key={i}><Td>{i + 1}</Td><Td>{t.symbol}</Td><Td>{t.side}</Td><Td>{cleanTime(t.entry_time)}</Td><Td>{t.entry_price ? `$${money(t.entry_price)}` : "-"}</Td><Td>{cleanTime(t.exit_time)}</Td><Td>{t.exit_price ? `$${money(t.exit_price)}` : "-"}</Td><Td>{t.exit_reason || "-"}</Td><Td><span style={t.result === "WIN" ? { color: "#22c55e", fontWeight: 900 } : t.result === "LOSS" ? { color: "#ef4444", fontWeight: 900 } : { color: "#f59e0b", fontWeight: 900 }}>{t.result}</span></Td><Td>{t.r || "-"}</Td></tr>)}</tbody></table></div>; }

const panelStyle: CSSProperties = { background: "#111827", border: "1px solid #334155", borderRadius: 14, padding: 18, marginBottom: 16 };
const h2Style: CSSProperties = { marginTop: 0, marginBottom: 12, fontSize: 18 };
const inputStyle: CSSProperties = { background: "#0f172a", color: "#e5e7eb", border: "1px solid #475569", borderRadius: 8, padding: "10px 12px" };
const cardStyle: CSSProperties = { background: "#111827", border: "1px solid #334155", borderRadius: 14, padding: 16 };
const miniStyle: CSSProperties = { background: "#0f172a", border: "1px solid #334155", borderRadius: 10, padding: 12, minHeight: 48 };
