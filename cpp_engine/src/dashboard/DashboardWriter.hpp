#pragma once
#include "../trading/Portfolio.hpp"
#include <algorithm>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

struct DashboardTradeRecord {
    uint64_t id = 0;
    std::string time;
    std::string symbol;
    std::string side = "BUY";
    double qty = 0.0;
    double entry = 0.0;
    double exit = 0.0;
    double stop = 0.0;
    double target1 = 0.0;
    double target2 = 0.0;
    std::string result = "OPEN";
    double r = 0.0;
    double pnl = 0.0;
    std::string reason;
};

struct DashboardEventRecord {
    std::string time;
    std::string type;
    std::string message;
};

struct DashboardTradeState {
    bool open_trade = false;
    std::string open_symbol;
    std::string open_side = "BUY";
    double open_qty = 0.0;
    double open_entry = 0.0;
    double open_stop = 0.0;
    double open_target1 = 0.0;
    double open_target2 = 0.0;
    double open_current_r = 0.0;
    double open_setup_score = 0.0;
    std::string open_reason;

    uint64_t total_trades = 0;
    uint64_t wins = 0;
    uint64_t losses = 0;
    uint64_t breakevens = 0;
    double gross_r = 0.0;
    double avg_r = 0.0;
    double best_r = 0.0;
    double worst_r = 0.0;
    double win_rate = 0.0;
    double profit_factor = 0.0;
    double expectancy_r = 0.0;
    uint64_t max_consecutive_wins = 0;
    uint64_t max_consecutive_losses = 0;
    uint64_t current_consecutive_wins = 0;
    uint64_t current_consecutive_losses = 0;

    std::string last_action = "NONE";
    std::string last_result = "NONE";
    std::string last_symbol;
    std::string last_side;
    double last_entry = 0.0;
    double last_exit = 0.0;
    double last_stop = 0.0;
    double last_target1 = 0.0;
    double last_target2 = 0.0;
    double last_r = 0.0;
    double last_setup_score = 0.0;
    std::string last_reason;

    std::vector<DashboardTradeRecord> trade_history;
    std::vector<DashboardEventRecord> event_log;
    std::vector<double> equity_curve;
};

class DashboardWriter {
public:
    explicit DashboardWriter(std::string dir = "dashboard") : dir_(std::move(dir)) {
        std::filesystem::create_directories(dir_);
        write_html();
    }

    void write_snapshot(uint64_t processed, uint64_t signals, const std::string& mode,
                        const Portfolio& portfolio, double equity, double daily_pnl,
                        double risk_utilization = 0.0, double p95_engine_us = 0.0,
                        double p99_engine_us = 0.0,
                        const DashboardTradeState& trade = DashboardTradeState{}) {
        std::ofstream out(dir_ + "/snapshot.json", std::ios::out | std::ios::trunc);
        out << "{\n"
            << "  \"mode\": \"" << esc(mode) << "\",\n"
            << "  \"processed\": " << processed << ",\n"
            << "  \"signals\": " << signals << ",\n"
            << "  \"equity\": " << equity << ",\n"
            << "  \"daily_pnl\": " << daily_pnl << ",\n"
            << "  \"realized_pnl\": " << portfolio.total_realized_pnl() << ",\n"
            << "  \"unrealized_pnl\": " << portfolio.total_unrealized_pnl() << ",\n"
            << "  \"gross_notional\": " << portfolio.gross_notional() << ",\n"
            << "  \"open_positions\": " << portfolio.open_position_count() << ",\n"
            << "  \"risk_utilization\": " << risk_utilization << ",\n"
            << "  \"p95_engine_us\": " << p95_engine_us << ",\n"
            << "  \"p99_engine_us\": " << p99_engine_us << ",\n"
            << "  \"trade_stats\": {"
            << "\"open_trade\":" << (trade.open_trade ? "true" : "false")
            << ",\"open_symbol\":\"" << esc(trade.open_symbol) << "\""
            << ",\"open_side\":\"" << esc(trade.open_side) << "\""
            << ",\"open_qty\":" << trade.open_qty
            << ",\"open_entry\":" << trade.open_entry
            << ",\"open_stop\":" << trade.open_stop
            << ",\"open_target1\":" << trade.open_target1
            << ",\"open_target2\":" << trade.open_target2
            << ",\"open_current_r\":" << trade.open_current_r
            << ",\"open_setup_score\":" << trade.open_setup_score
            << ",\"open_reason\":\"" << esc(trade.open_reason) << "\""
            << ",\"total_trades\":" << trade.total_trades
            << ",\"wins\":" << trade.wins
            << ",\"losses\":" << trade.losses
            << ",\"breakevens\":" << trade.breakevens
            << ",\"gross_r\":" << trade.gross_r
            << ",\"avg_r\":" << trade.avg_r
            << ",\"best_r\":" << trade.best_r
            << ",\"worst_r\":" << trade.worst_r
            << ",\"win_rate\":" << trade.win_rate
            << ",\"profit_factor\":" << trade.profit_factor
            << ",\"expectancy_r\":" << trade.expectancy_r
            << ",\"max_consecutive_wins\":" << trade.max_consecutive_wins
            << ",\"max_consecutive_losses\":" << trade.max_consecutive_losses
            << ",\"last_action\":\"" << esc(trade.last_action) << "\""
            << ",\"last_result\":\"" << esc(trade.last_result) << "\""
            << ",\"last_symbol\":\"" << esc(trade.last_symbol) << "\""
            << ",\"last_side\":\"" << esc(trade.last_side) << "\""
            << ",\"last_entry\":" << trade.last_entry
            << ",\"last_exit\":" << trade.last_exit
            << ",\"last_stop\":" << trade.last_stop
            << ",\"last_target1\":" << trade.last_target1
            << ",\"last_target2\":" << trade.last_target2
            << ",\"last_r\":" << trade.last_r
            << ",\"last_setup_score\":" << trade.last_setup_score
            << ",\"last_reason\":\"" << esc(trade.last_reason) << "\""
            << "},\n";

        out << "  \"positions\": [";
        bool first = true;
        for (const auto& kv : portfolio.positions()) {
            const auto& p = kv.second;
            if (!first) out << ",";
            first = false;
            out << "{\"symbol\":\"" << esc(p.symbol) << "\",\"qty\":" << p.quantity
                << ",\"avg\":" << p.avg_price << ",\"last\":" << portfolio.last_price(p.symbol)
                << ",\"realized\":" << p.realized_pnl << ",\"unrealized\":" << p.unrealized_pnl << "}";
        }
        out << "],\n";

        out << "  \"trade_history\": [";
        first = true;
        for (const auto& tr : trade.trade_history) {
            if (!first) out << ",";
            first = false;
            out << "{\"id\":" << tr.id
                << ",\"time\":\"" << esc(tr.time) << "\""
                << ",\"symbol\":\"" << esc(tr.symbol) << "\""
                << ",\"side\":\"" << esc(tr.side) << "\""
                << ",\"qty\":" << tr.qty
                << ",\"entry\":" << tr.entry
                << ",\"exit\":" << tr.exit
                << ",\"stop\":" << tr.stop
                << ",\"target1\":" << tr.target1
                << ",\"target2\":" << tr.target2
                << ",\"result\":\"" << esc(tr.result) << "\""
                << ",\"r\":" << tr.r
                << ",\"pnl\":" << tr.pnl
                << ",\"reason\":\"" << esc(tr.reason) << "\"}";
        }
        out << "],\n";

        out << "  \"event_log\": [";
        first = true;
        for (const auto& ev : trade.event_log) {
            if (!first) out << ",";
            first = false;
            out << "{\"time\":\"" << esc(ev.time) << "\",\"type\":\"" << esc(ev.type)
                << "\",\"message\":\"" << esc(ev.message) << "\"}";
        }
        out << "],\n";

        out << "  \"equity_curve\": [";
        first = true;
        for (double e : trade.equity_curve) {
            if (!first) out << ",";
            first = false;
            out << e;
        }
        out << "]\n}\n";
        out.close();
        write_embedded_snapshot_html();
    }

private:
    static std::string esc(const std::string& s) {
        std::string r; r.reserve(s.size());
        for (char c : s) {
            if (c == '"') r += "\\\"";
            else if (c == '\\') r += "\\\\";
            else if (c == '\n') r += "\\n";
            else r += c;
        }
        return r;
    }

    void write_embedded_snapshot_html() {
        std::ifstream js(dir_ + "/snapshot.json");
        std::string data((std::istreambuf_iterator<char>(js)), std::istreambuf_iterator<char>());
        std::ofstream html(dir_ + "/snapshot_static.html", std::ios::out | std::ios::trunc);
        html << "<!doctype html><html><head><meta charset=\"utf-8\"><title>PRISMFlow Snapshot</title></head><body><pre id=\"p\"></pre><script>document.getElementById('p').textContent=JSON.stringify(" << data << ",null,2);</script></body></html>";
    }

    void write_html() {
        std::ofstream html(dir_ + "/index.html", std::ios::out | std::ios::trunc);
        html << R"HTML(<!doctype html><html><head><meta charset="utf-8"><title>PRISMFlow Dashboard</title>
<style>
body{font-family:Arial;margin:32px;background:#0b1020;color:#e8eefc}.grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px}.card{background:#151d35;padding:18px;border-radius:12px;margin:12px 0;box-shadow:0 0 0 1px #263457}.k{font-size:13px;color:#9db0d5}.v{font-size:25px;font-weight:700}.ok{color:#7CFC98}.bad{color:#ff6b6b}.warn{color:#ffd166}table{width:100%;border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #303a5f;text-align:left}.small{color:#9db0d5;font-size:13px}.pill{display:inline-block;padding:3px 8px;border-radius:12px;background:#263457}.buy{color:#7CFC98}.sell{color:#ff8a8a}.scroll{max-height:360px;overflow:auto}.mono{font-family:Consolas,monospace}.bar{height:80px;display:flex;align-items:flex-end;gap:3px}.bar span{display:inline-block;background:#6478ff;min-width:8px;border-radius:3px 3px 0 0}
</style></head>
<body><h1>PRISMFlow C++ Heavy Live Paper Trading Dashboard v5</h1><p class="small">Live Binance feed → C++ PRISM → Risk → PositionSizer → PaperBroker → Ledger/EventStore → Trade Journal → Dashboard</p><div id="root">Waiting for snapshot.json...</div>
<script>
function fmt(n){return Number(n||0).toLocaleString(undefined,{maximumFractionDigits:4});}
function cls(v){return Number(v||0)>=0?'ok':'bad';}
function sideCls(s){return String(s||'').toLowerCase()==='sell'?'sell':'buy';}
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function equityBars(arr){if(!arr||!arr.length)return '<span class="small">No equity history yet</span>';let mn=Math.min(...arr),mx=Math.max(...arr),rng=Math.max(1e-9,mx-mn);return '<div class="bar">'+arr.slice(-80).map(v=>`<span title="${fmt(v)}" style="height:${10+70*(v-mn)/rng}px"></span>`).join('')+'</div><div class="small">Start ${fmt(arr[0])} → Current ${fmt(arr[arr.length-1])}</div>';}
async function load(){try{const r=await fetch('snapshot.json?x='+Date.now());if(!r.ok)throw new Error(r.status);const d=await r.json();const t=d.trade_stats||{};const hist=d.trade_history||[];const events=d.event_log||[];let h='<div class="grid">';
h+=`<div class="card"><div class="k">Mode</div><div class="v ok">${esc(d.mode)}</div></div>`;
h+=`<div class="card"><div class="k">Processed</div><div class="v">${fmt(d.processed)}</div></div>`;
h+=`<div class="card"><div class="k">PRISM Signals</div><div class="v warn">${fmt(d.signals)}</div></div>`;
h+=`<div class="card"><div class="k">Open Trade</div><div class="v ${t.open_trade?'ok':'bad'}">${t.open_trade?'YES':'NO'}</div></div>`;
h+=`<div class="card"><div class="k">Total Trades</div><div class="v">${fmt(t.total_trades)}</div></div>`;
h+=`<div class="card"><div class="k">Wins / Losses / BE</div><div class="v"><span class="ok">${fmt(t.wins)}</span> / <span class="bad">${fmt(t.losses)}</span> / ${fmt(t.breakevens)}</div></div>`;
h+=`<div class="card"><div class="k">Gross R / Avg R</div><div class="v ${cls(t.gross_r)}">${fmt(t.gross_r)}R / ${fmt(t.avg_r)}R</div></div>`;
h+=`<div class="card"><div class="k">Last Result</div><div class="v ${cls(t.last_r)}">${esc(t.last_result||'NONE')} ${fmt(t.last_r)}R</div></div>`;
h+=`<div class="card"><div class="k">Equity</div><div class="v">${fmt(d.equity)}</div></div>`;
h+=`<div class="card"><div class="k">Realized PnL</div><div class="v ${cls(d.realized_pnl)}">${fmt(d.realized_pnl)}</div></div>`;
h+=`<div class="card"><div class="k">Unrealized PnL</div><div class="v ${cls(d.unrealized_pnl)}">${fmt(d.unrealized_pnl)}</div></div>`;
h+=`<div class="card"><div class="k">Risk Utilization</div><div class="v warn">${fmt((d.risk_utilization||0)*100)}%</div></div>`;
h+='</div>';
h+=`<div class="card"><b>Gross Notional:</b> ${fmt(d.gross_notional)} &nbsp; <b>P95 Engine:</b> ${fmt(d.p95_engine_us)} µs &nbsp; <b>P99 Engine:</b> ${fmt(d.p99_engine_us)} µs</div>`;
h+=`<div class="card"><h2>Current PRISM Trade Plan</h2><table><tr><th>Status</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Stop</th><th>Target 1</th><th>Target 2</th><th>Current R</th><th>Score</th><th>Reason</th></tr>`;
h+=`<tr><td>${t.open_trade?'OPEN':'FLAT'}</td><td>${esc(t.open_symbol||'-')}</td><td class="${sideCls(t.open_side)}">${esc(t.open_side||'-')}</td><td>${fmt(t.open_qty)}</td><td>${fmt(t.open_entry)}</td><td>${fmt(t.open_stop)}</td><td>${fmt(t.open_target1)}</td><td>${fmt(t.open_target2)}</td><td class="${cls(t.open_current_r)}">${fmt(t.open_current_r)}R</td><td>${fmt(t.open_setup_score)}</td><td>${esc(t.open_reason||'-')}</td></tr></table></div>`;
h+=`<div class="card"><h2>Last Order / Exit</h2><table><tr><th>Action</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>Stop</th><th>T1</th><th>T2</th><th>Result</th><th>R</th><th>Reason</th></tr>`;
h+=`<tr><td>${esc(t.last_action||'-')}</td><td>${esc(t.last_symbol||'-')}</td><td class="${sideCls(t.last_side)}">${esc(t.last_side||'-')}</td><td>${fmt(t.last_entry)}</td><td>${fmt(t.last_exit)}</td><td>${fmt(t.last_stop)}</td><td>${fmt(t.last_target1)}</td><td>${fmt(t.last_target2)}</td><td>${esc(t.last_result||'-')}</td><td class="${cls(t.last_r)}">${fmt(t.last_r)}R</td><td>${esc(t.last_reason||'-')}</td></tr></table></div>`;
h+=`<div class="card"><h2>Full Trade History / Journal</h2><div class="scroll"><table><tr><th>#</th><th>Time</th><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>Stop</th><th>T1</th><th>T2</th><th>Result</th><th>R</th><th>PnL</th><th>Reason</th></tr>`;
if(hist.length===0) h+='<tr><td colspan="14" class="small">No closed trades yet. Run demo mode or keep live engine running until PRISM exits a paper trade.</td></tr>'; else hist.slice().reverse().forEach(x=>h+=`<tr><td>${x.id}</td><td>${esc(x.time)}</td><td>${esc(x.symbol)}</td><td class="${sideCls(x.side)}">${esc(x.side)}</td><td>${fmt(x.qty)}</td><td>${fmt(x.entry)}</td><td>${fmt(x.exit)}</td><td>${fmt(x.stop)}</td><td>${fmt(x.target1)}</td><td>${fmt(x.target2)}</td><td class="${x.result==='WIN'?'ok':x.result==='LOSS'?'bad':'warn'}">${esc(x.result)}</td><td class="${cls(x.r)}">${fmt(x.r)}R</td><td class="${cls(x.pnl)}">${fmt(x.pnl)}</td><td>${esc(x.reason)}</td></tr>`);
h+='</table></div></div>';
h+=`<div class="card"><h2>Trade Analytics</h2><div class="grid"><div><b>Win Rate</b><br><span class="v">${fmt(t.win_rate)}%</span></div><div><b>Best / Worst R</b><br><span class="v ${cls(t.best_r)}">${fmt(t.best_r)}R</span> / <span class="v ${cls(t.worst_r)}">${fmt(t.worst_r)}R</span></div><div><b>Profit Factor</b><br><span class="v">${fmt(t.profit_factor)}</span></div><div><b>Expectancy</b><br><span class="v ${cls(t.expectancy_r)}">${fmt(t.expectancy_r)}R</span></div><div><b>Max Consecutive Wins</b><br><span class="v ok">${fmt(t.max_consecutive_wins)}</span></div><div><b>Max Consecutive Losses</b><br><span class="v bad">${fmt(t.max_consecutive_losses)}</span></div></div></div>`;
h+=`<div class="card"><h2>Equity Curve</h2>${equityBars(d.equity_curve||[])}</div>`;
h+=`<div class="card"><h2>Positions</h2><table><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Last</th><th>Realized</th><th>Unrealized</th></tr>`;(d.positions||[]).forEach(p=>h+=`<tr><td>${esc(p.symbol)}</td><td>${fmt(p.qty)}</td><td>${fmt(p.avg)}</td><td>${fmt(p.last)}</td><td class="${cls(p.realized)}">${fmt(p.realized)}</td><td class="${cls(p.unrealized)}">${fmt(p.unrealized)}</td></tr>`);h+='</table></div>';
h+=`<div class="card"><h2>Event Log</h2><div class="scroll"><table><tr><th>Time</th><th>Type</th><th>Message</th></tr>`;events.slice().reverse().forEach(e=>h+=`<tr><td class="mono">${esc(e.time)}</td><td><span class="pill">${esc(e.type)}</span></td><td>${esc(e.message)}</td></tr>`);h+='</table></div></div>';
document.getElementById('root').innerHTML=h;}catch(e){document.getElementById('root').innerHTML='Waiting for snapshot.json... Start dashboard server and keep live paper engine running.';}}
setInterval(load,1000);load();
</script></body></html>)HTML";
    }
    std::string dir_;
};
