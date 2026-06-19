'use client';
import {useEffect,useMemo,useState} from 'react';
import {api} from '../../lib/api';
import {Area,AreaChart,Bar,BarChart,CartesianGrid,Cell,Pie,PieChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

type Job={id:string; mode:string; status:string; created_at:string; timeframe?:string; symbols_json?:string; display_strategy_id?:string; user_strategy_id?:string; strategy_code?:string; strategy_id?:string};
const th:any={textAlign:'left', padding:'10px 8px', borderBottom:'1px solid #334155', color:'#94a3b8'};
const td:any={padding:'9px 8px', borderBottom:'1px solid #1e293b'};
function fmt(n:any,d=2){const x=Number(n??0); return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function parseSymbols(j:Job){try{return JSON.parse(j.symbols_json||'[]').join(', ')}catch{return '-'}}
function displayStrategy(j:Job){return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'STRATEGY'}
function bucket(values:number[]){const rows=[{name:'<-1R',trades:0},{name:'-1R..0',trades:0},{name:'0..1R',trades:0},{name:'1R..2R',trades:0},{name:'2R+',trades:0}]; values.forEach(v=>{if(v<-1)rows[0].trades++; else if(v<0)rows[1].trades++; else if(v<1)rows[2].trades++; else if(v<2)rows[3].trades++; else rows[4].trades++;}); return rows}
function advice(data:any){if(!data)return 'Select a completed job to see analytics advice.'; const avg=Number(data.avg_R||0), wr=(Number(data.wins||0)/Math.max(1,Number(data.values?.length||0)))*100; if(avg>0.15&&wr>35)return 'This test shows positive expectancy. Next step: validate on more symbols/time periods before changing rules.'; if(avg<0)return 'The strategy is not ready. Focus on reducing weak setups, drawdown clusters, and false breakouts before scaling.'; return 'The strategy is borderline. Keep rules stable and increase sample size before judging.'}

export default function Analytics(){
  const [jobs,setJobs]=useState<Job[]>([]),[data,setData]=useState<any>(null),[curve,setCurve]=useState<any[]>([]),[msg,setMsg]=useState('');
  useEffect(()=>{api('/jobs/').then((r:any)=>setJobs(Array.isArray(r)?r:(r.jobs||[]))).catch(e=>setMsg('Cannot reach QuantOS API. Start the backend and refresh. '+e.message))},[]);
  async function load(id:string){
    if(!id) return; setMsg('Loading analytics...');
    try{ const [r,c]=await Promise.all([api(`/analytics/${id}/r-multiples`), api(`/analytics/${id}/equity-curve`)]); setData(r); setCurve(Array.isArray(c)?c:[]); setMsg(''); }
    catch(e:any){setMsg('Analytics load failed: '+e.message)}
  }
  const selected=useMemo(()=>jobs.find(j=>j.id===data?.job_id),[jobs,data]);
  const values=(data?.values||[]).map((x:any)=>Number(x)).filter((x:number)=>Number.isFinite(x));
  const pie=[{name:'Wins',value:Number(data?.wins||0)},{name:'Losses',value:Number(data?.losses||0)},{name:'Flat',value:Math.max(0,values.length-Number(data?.wins||0)-Number(data?.losses||0))}].filter(x=>x.value>0);
  const equity=curve.map((r,i)=>({trade:i+1,equity:Number(r.equity_R||0)}));
  const dist=bucket(values);
  return <>
    <div className="hero"><h1>Advanced Analytics</h1><p className="muted">Visual report for equity, drawdown, R distribution, win/loss mix, and strategy advice.</p></div>
    {msg && <div className="card" style={{borderColor:'#7f1d1d', color:msg.startsWith('Cannot')?'#f87171':'#cbd5e1'}}>{msg}</div>}
    <div className="card"><label>Select Job<select onChange={e=>load(e.target.value)} defaultValue=""><option value="">Choose completed job...</option>{jobs.filter(j=>j.status==='completed').map(j=><option key={j.id} value={j.id}>{displayStrategy(j)} · {j.mode} · {parseSymbols(j)} · {j.timeframe||''}</option>)}</select></label></div>
    {data&&<>
      <div className="grid">
        <div className="card"><h3>Gross R</h3><div className="metric">{fmt(data.gross_R)}R</div></div>
        <div className="card"><h3>Avg R</h3><div className="metric">{fmt(data.avg_R,3)}R</div></div>
        <div className="card"><h3>Wins / Losses</h3><div className="metric">{data.wins}/{data.losses}</div></div>
        <div className="card"><h3>Total Trades</h3><div className="metric">{values.length}</div></div>
      </div>
      <div className="card"><h2>QuantOS Advice</h2><p className="muted">{advice(data)}</p></div>
      <div className="grid">
        <div className="card"><h2>Equity Curve</h2><p className="muted">Running cumulative R after each trade.</p><ResponsiveContainer width="100%" height={240}><AreaChart data={equity}><CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a"/><XAxis dataKey="trade" stroke="#94a3b8"/><YAxis stroke="#94a3b8"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #334155'}}/><Area type="monotone" dataKey="equity" strokeWidth={2}/></AreaChart></ResponsiveContainer></div>
        <div className="card"><h2>R Distribution</h2><p className="muted">Shows if losses are controlled and winners are meaningful.</p><ResponsiveContainer width="100%" height={240}><BarChart data={dist}><CartesianGrid strokeDasharray="3 3" stroke="#2a2a4a"/><XAxis dataKey="name" stroke="#94a3b8"/><YAxis stroke="#94a3b8"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #334155'}}/><Bar dataKey="trades" radius={[6,6,0,0]}/></BarChart></ResponsiveContainer></div>
        <div className="card"><h2>Win/Loss Mix</h2><p className="muted">Simple view of outcome composition.</p><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={pie} dataKey="value" nameKey="name" outerRadius={82} label>{pie.map((_,i)=><Cell key={i}/>)}</Pie><Tooltip contentStyle={{background:'#111827',border:'1px solid #334155'}}/></PieChart></ResponsiveContainer></div>
      </div>
      <div className="card"><h2>Trade Table</h2><p className="muted">Detailed running equity after each trade.</p><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>Trade #</th><th style={th}>Trade ID</th><th style={th}>Equity R</th><th style={th}>Status</th></tr></thead><tbody>{curve.map((r,i)=><tr key={i}><td style={td}>{i+1}</td><td style={td}>{r.trade_id||'-'}</td><td style={td}>{fmt(r.equity_R,3)}R</td><td style={td}>{Number(r.equity_R)>=0?'Positive':'Negative'}</td></tr>)}</tbody></table></div></div>
    </>}
  </>
}