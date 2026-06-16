'use client';

import {useEffect,useState} from 'react';
import {api} from '../../lib/api';

const th:any={textAlign:'left', padding:'10px 8px', borderBottom:'1px solid #334155', color:'#94a3b8'};
const td:any={padding:'9px 8px', borderBottom:'1px solid #1e293b'};
function fmt(n:any,d=2){const x=Number(n??0); return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function syms(j:any){try{return JSON.parse(j.symbols_json||'[]').join(', ')}catch{return '-'}}
function displayStrategy(j:any){return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'Strategy'}

export default function Backtests(){
  const [jobs,setJobs]=useState<any[]>([]);
  const [selected,setSelected]=useState<any>(null);
  const [summary,setSummary]=useState<any>(null);
  const [trades,setTrades]=useState<any[]>([]);
  
  const [msg,setMsg]=useState('');

  async function refresh(){
    try{ setMsg('Loading jobs...'); const r: any = await api('/jobs/'); setJobs(Array.isArray(r)?r:(r.jobs||[])); setMsg(''); }
    catch(e:any){ setMsg('Jobs load failed: ' + e.message); }
  }
  useEffect(()=>{refresh()},[]);

  async function load(j:any){
    try{ setSelected(j); setSummary(null); setTrades([]);  setMsg('Loading reports...');
      const [s,t] = await Promise.all([api(`/reports/${j.id}/summary`), api(`/reports/${j.id}/trade-log`)]);
      setSummary(s); setTrades(Array.isArray(t) ? t : []); setMsg(''); }
    catch(e:any){ setMsg('Report load failed: ' + e.message); }
  }

  return <>
    <div className="hero"><h1>Backtest Results</h1></div>
    {msg && <div className="card">{msg}</div>}
    <div className="card"><h2>Jobs</h2><button onClick={refresh}>Refresh Jobs</button><br/><br/><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>Strategy ID</th><th style={th}>Symbol</th><th style={th}>Status</th><th style={th}>Mode</th><th style={th}>Timeframe</th><th style={th}>Created</th><th style={th}>Action</th></tr></thead><tbody>{jobs.map(j=><tr key={j.id}><td style={td}>{displayStrategy(j)}</td><td style={td}>{syms(j)}</td><td style={td}>{j.status}</td><td style={td}>{j.mode}</td><td style={td}>{j.timeframe}</td><td style={td}>{j.created_at}</td><td style={td}><button onClick={()=>load(j)} disabled={j.status!=='completed'}>Open Report</button></td></tr>)}</tbody></table></div></div>
    {selected && <div className="card"><h2>Selected Job</h2><div className="grid"><div><b>Strategy ID</b><div className="metric">{displayStrategy(selected)}</div></div><div><b>Symbol</b><div className="metric">{syms(selected)}</div></div><div><b>Status</b><div className="metric">{selected.status}</div></div><div><b>Timeframe</b><div className="metric">{selected.timeframe}</div></div></div>{selected.error_message&&<p style={{color:'#f87171'}}>{selected.error_message}</p>}</div>}
    {summary && <div className="card"><h2>Summary</h2><div className="grid"><div><b>Total Trades</b><div className="metric">{summary.total_trades ?? 0}</div></div><div><b>Win Rate</b><div className="metric">{Number((summary.win_rate ?? 0) * 100).toFixed(2)}%</div></div><div><b>Gross R</b><div className="metric">{fmt(summary.gross_R)}R</div></div><div><b>Avg R</b><div className="metric">{fmt(summary.average_R)}R</div></div><div><b>Profit Factor</b><div className="metric">{fmt(summary.profit_factor)}</div></div><div><b>Max DD</b><div className="metric">{fmt(summary.max_drawdown_in_R)}R</div></div></div></div>}
    {trades.length > 0 && <div className="card"><h2>Trade Log</h2><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>ID</th><th style={th}>Entry Time</th><th style={th}>Entry</th><th style={th}>Exit Time</th><th style={th}>Exit</th><th style={th}>Exit Reason</th><th style={th}>Result</th><th style={th}>R</th></tr></thead><tbody>{trades.map((t:any)=><tr key={t.trade_id}><td style={td}>{t.trade_id}</td><td style={td}>{t.entry_time}</td><td style={td}>${fmt(t.entry_price)}</td><td style={td}>{t.exit_time}</td><td style={td}>${fmt(t.exit_price)}</td><td style={td}>{String(t.exit_reason||'').replaceAll('_',' ')}</td><td style={td}>{Number(t.r_multiple)>=0?'WIN':'LOSS'}</td><td style={td}>{fmt(t.r_multiple,3)}</td></tr>)}</tbody></table></div></div>}
  </>;
}
