'use client';
import {useEffect,useMemo,useState} from 'react';
import {api} from '../../lib/api';

type Job={id:string; mode:string; status:string; created_at:string; timeframe?:string; symbols_json?:string; display_strategy_id?:string; user_strategy_id?:string; strategy_code?:string; strategy_id?:string};
const th:any={textAlign:'left', padding:'10px 8px', borderBottom:'1px solid #334155', color:'#94a3b8'};
const td:any={padding:'9px 8px', borderBottom:'1px solid #1e293b'};
function fmt(n:any,d=2){const x=Number(n??0); return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function parseSymbols(j:Job){try{return JSON.parse(j.symbols_json||'[]').join(', ')}catch{return '-'}}
function displayStrategy(j:Job){return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'STRATEGY'}

export default function Analytics(){
  const [jobs,setJobs]=useState<Job[]>([]),[data,setData]=useState<any>(null),[curve,setCurve]=useState<any[]>([]),[msg,setMsg]=useState('');
  useEffect(()=>{api('/jobs/').then((r:any)=>setJobs(Array.isArray(r)?r:(r.jobs||[]))).catch(e=>setMsg('Cannot reach QuantOS API. Start the backend and refresh. '+e.message))},[]);
  async function load(id:string){
    if(!id) return; setMsg('Loading analytics...');
    try{ const [r,c]=await Promise.all([api(`/analytics/${id}/r-multiples`), api(`/analytics/${id}/equity-curve`)]); setData(r); setCurve(Array.isArray(c)?c:[]); setMsg(''); }
    catch(e:any){setMsg('Analytics load failed: '+e.message)}
  }
  const selected=useMemo(()=>jobs.find(j=>j.id===data?.job_id),[jobs,data]);
  return <>
    <div className="hero"><h1>R-Multiple Analytics</h1><p className="muted">Clean report view for Gross R, average R, wins/losses and equity curve.</p></div>
    {msg && <div className="card" style={{borderColor:'#7f1d1d', color:msg.startsWith('Cannot')?'#f87171':'#cbd5e1'}}>{msg}</div>}
    <div className="card"><label>Select Job<select onChange={e=>load(e.target.value)} defaultValue=""><option value="">Choose completed job...</option>{jobs.filter(j=>j.status==='completed').map(j=><option key={j.id} value={j.id}>{displayStrategy(j)} · {j.mode} · {parseSymbols(j)} · {j.timeframe||''}</option>)}</select></label></div>
    {data&&<>
      <div className="grid">
        <div className="card"><h3>Gross R</h3><div className="metric">{fmt(data.gross_R)}R</div></div>
        <div className="card"><h3>Avg R</h3><div className="metric">{fmt(data.avg_R,3)}R</div></div>
        <div className="card"><h3>Wins / Losses</h3><div className="metric">{data.wins}/{data.losses}</div></div>
        <div className="card"><h3>Total Trades</h3><div className="metric">{data.values?.length||0}</div></div>
      </div>
      <div className="card"><h2>Equity Curve</h2><p className="muted">Running equity in R after each trade.</p><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>Trade #</th><th style={th}>Trade ID</th><th style={th}>Equity R</th><th style={th}>Status</th></tr></thead><tbody>{curve.map((r,i)=><tr key={i}><td style={td}>{i+1}</td><td style={td}>{r.trade_id||'-'}</td><td style={td}>{fmt(r.equity_R,3)}R</td><td style={td}>{Number(r.equity_R)>=0?'Positive':'Negative'}</td></tr>)}</tbody></table></div></div>
    </>}
  </>
}
