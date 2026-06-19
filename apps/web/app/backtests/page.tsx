'use client';

import {useEffect,useMemo,useState} from 'react';
import {api} from '../../lib/api';
import {Area,AreaChart,Bar,BarChart,CartesianGrid,Cell,Pie,PieChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

const th:any={textAlign:'left', padding:'10px 8px', borderBottom:'1px solid #334155', color:'#94a3b8'};
const td:any={padding:'9px 8px', borderBottom:'1px solid #1e293b'};
function fmt(n:any,d=2){const x=Number(n??0); return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function syms(j:any){try{return JSON.parse(j.symbols_json||'[]').join(', ')}catch{return '-'}}
function displayStrategy(j:any){return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'Strategy'}
function bucketR(trades:any[]){const rows=[{name:'Big Loss',trades:0},{name:'Small Loss',trades:0},{name:'Flat',trades:0},{name:'Good Win',trades:0},{name:'Big Win',trades:0}]; trades.forEach(t=>{const r=Number(t.r_multiple||0); if(r<=-1)rows[0].trades++; else if(r<0)rows[1].trades++; else if(r<0.5)rows[2].trades++; else if(r<2)rows[3].trades++; else rows[4].trades++;}); return rows}
function equityCurve(trades:any[]){let eq=0; return trades.map((t,i)=>{eq+=Number(t.r_multiple||0); return {trade:i+1,equity:Number(eq.toFixed(3))}})}
function exitReasonData(trades:any[]){const m:Record<string,number>={}; trades.forEach(t=>{const k=String(t.exit_reason||'Unknown').replaceAll('_',' '); m[k]=(m[k]||0)+1}); return Object.entries(m).map(([name,value])=>({name,value})).slice(0,8)}
function backtestAdvice(summary:any,trades:any[]){if(!summary)return 'Open a completed report to get advice.'; const avg=Number(summary.average_R||0), pf=Number(summary.profit_factor||0), wr=Number(summary.win_rate||0)*100; if(avg>0&&pf>1.2)return `Promising test: positive expectancy (${fmt(avg,3)}R/trade) and profit factor ${fmt(pf)}. Validate with more market regimes before trusting it.`; if(avg<0||pf<1)return `Not ready yet: expectancy is ${fmt(avg,3)}R/trade and win rate is ${fmt(wr,1)}%. Reduce weak entries and check where losses cluster.`; return 'Borderline result. Do not optimize randomly. Keep rules stable and run a larger sample.'}

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
    try{ setSelected(j); setSummary(null); setTrades([]); setMsg('Loading reports...');
      const [s,t] = await Promise.all([api(`/reports/${j.id}/summary`), api(`/reports/${j.id}/trade-log`)]);
      setSummary(s); setTrades(Array.isArray(t) ? t : []); setMsg(''); }
    catch(e:any){ setMsg('Report load failed: ' + e.message); }
  }

  const rDist=useMemo(()=>bucketR(trades),[trades]);
  const equity=useMemo(()=>equityCurve(trades),[trades]);
  const exitMix=useMemo(()=>exitReasonData(trades),[trades]);
  const winLoss=useMemo(()=>{
    const wins=trades.filter(t=>Number(t.r_multiple)>=0).length;
    const losses=trades.length-wins;
    return [{name:'Wins',value:wins},{name:'Losses',value:losses}].filter(x=>x.value>0);
  },[trades]);

  return <>
    <div className="hero"><h1>Backtest Results</h1><p className="muted">Open a completed job to view metrics, equity curve, R-distribution, win/loss mix, and exit-reason breakdown.</p></div>
    {msg && <div className="card">{msg}</div>}
    <div className="card"><h2>Jobs</h2><button onClick={refresh}>Refresh Jobs</button><br/><br/><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>Strategy ID</th><th style={th}>Symbol</th><th style={th}>Status</th><th style={th}>Mode</th><th style={th}>Timeframe</th><th style={th}>Created</th><th style={th}>Action</th></tr></thead><tbody>{jobs.map(j=><tr key={j.id}><td style={td}>{displayStrategy(j)}</td><td style={td}>{syms(j)}</td><td style={td}>{j.status}</td><td style={td}>{j.mode}</td><td style={td}>{j.timeframe}</td><td style={td}>{j.created_at}</td><td style={td}><button onClick={()=>load(j)} disabled={j.status!=='completed'}>Open Report</button></td></tr>)}</tbody></table></div></div>
    {selected && <div className="card"><h2>Selected Job</h2><div className="grid"><div><b>Strategy ID</b><div className="metric">{displayStrategy(selected)}</div></div><div><b>Symbol</b><div className="metric">{syms(selected)}</div></div><div><b>Status</b><div className="metric">{selected.status}</div></div><div><b>Timeframe</b><div className="metric">{selected.timeframe}</div></div></div>{selected.error_message&&<p style={{color:'#f87171'}}>{selected.error_message}</p>}</div>}
    {summary && <div className="card"><h2>Summary</h2><div className="grid"><div><b>Total Trades</b><div className="metric">{summary.total_trades ?? 0}</div></div><div><b>Win Rate</b><div className="metric">{Number((summary.win_rate ?? 0) * 100).toFixed(2)}%</div></div><div><b>Gross R</b><div className="metric">{fmt(summary.gross_R)}R</div></div><div><b>Avg R</b><div className="metric">{fmt(summary.average_R)}R</div></div><div><b>Profit Factor</b><div className="metric">{fmt(summary.profit_factor)}</div></div><div><b>Max DD</b><div className="metric">{fmt(summary.max_drawdown_in_R)}R</div></div></div></div>}
    {summary && <div className="card"><h2>Backtest Advice</h2><p className="muted">{backtestAdvice(summary,trades)}</p></div>}
    {trades.length > 0 && <div className="grid">
      <div className="card"><h2>Equity Curve</h2><p className="muted">Cumulative R after each closed trade.</p><ResponsiveContainer width="100%" height={240}><AreaChart data={equity}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Area type="monotone" dataKey="equity" stroke="#38bdf8" fill="#38bdf855" strokeWidth={3}/></AreaChart></ResponsiveContainer></div>
      <div className="card"><h2>R Distribution</h2><p className="muted">Are losses controlled and wins meaningful?</p><ResponsiveContainer width="100%" height={240}><BarChart data={rDist}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Bar dataKey="trades" fill="#a78bfa" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></div>
      <div className="card"><h2>Win/Loss Mix</h2><p className="muted">Outcome composition of this test.</p><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={winLoss} dataKey="value" nameKey="name" outerRadius={82} label>{winLoss.map((_,i)=><Cell key={i} fill={i===0?'#22c55e':'#ef4444'}/>)}</Pie><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/></PieChart></ResponsiveContainer></div>
      <div className="card"><h2>Exit Reasons</h2><p className="muted">What closes most trades?</p><ResponsiveContainer width="100%" height={240}><BarChart data={exitMix}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1" tick={{fontSize:10}}/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Bar dataKey="value" fill="#f59e0b" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></div>
    </div>}
    {trades.length > 0 && <div className="card"><h2>Trade Log</h2><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>ID</th><th style={th}>Entry Time</th><th style={th}>Entry</th><th style={th}>Exit Time</th><th style={th}>Exit</th><th style={th}>Exit Reason</th><th style={th}>Result</th><th style={th}>R</th></tr></thead><tbody>{trades.map((t:any)=><tr key={t.trade_id}><td style={td}>{t.trade_id}</td><td style={td}>{t.entry_time}</td><td style={td}>${fmt(t.entry_price)}</td><td style={td}>{t.exit_time}</td><td style={td}>${fmt(t.exit_price)}</td><td style={td}>{String(t.exit_reason||'').replaceAll('_',' ')}</td><td style={td}>{Number(t.r_multiple)>=0?'WIN':'LOSS'}</td><td style={td}>{fmt(t.r_multiple,3)}</td></tr>)}</tbody></table></div></div>}
  </>;
}