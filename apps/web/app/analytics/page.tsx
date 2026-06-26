'use client';
import {useEffect,useMemo,useState} from 'react';
import {api} from '../../lib/api';
import {Area,AreaChart,Bar,BarChart,CartesianGrid,Cell,Line,LineChart,Pie,PieChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts';

type Job={id:string; mode:string; status:string; created_at:string; timeframe?:string; symbols_json?:string; display_strategy_id?:string; user_strategy_id?:string; strategy_code?:string; strategy_id?:string};
const th:any={textAlign:'left',padding:'10px 8px',borderBottom:'1px solid #334155',color:'#94a3b8'};
const td:any={padding:'9px 8px',borderBottom:'1px solid #1e293b'};
const tip:any={background:'#111827',border:'1px solid #475569',color:'#e2e8f0'};
function fmt(n:any,d=2){const x=Number(n??0);return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function parseSymbols(j:Job){try{return JSON.parse(j.symbols_json||'[]').join(', ')}catch{return '-'}}
function displayStrategy(j:Job){return j.display_strategy_id||j.user_strategy_id||j.strategy_code||j.strategy_id||'STRATEGY'}
function bucket(values:number[]){const rows=[{name:'Big Loss',trades:0},{name:'Small Loss',trades:0},{name:'Flat',trades:0},{name:'Good Win',trades:0},{name:'Big Win',trades:0}];values.forEach(v=>{if(v<=-1)rows[0].trades++;else if(v<0)rows[1].trades++;else if(v<0.5)rows[2].trades++;else if(v<2)rows[3].trades++;else rows[4].trades++;});return rows}
function drawdown(equity:any[]){let peak=0;return equity.map(x=>{peak=Math.max(peak,Number(x.equity||0));return{trade:x.trade,drawdown:Number((Number(x.equity||0)-peak).toFixed(3))}})}
function rolling(values:number[],window=20){return values.map((_,i)=>{const s=values.slice(Math.max(0,i-window+1),i+1);const avg=s.reduce((a,b)=>a+b,0)/Math.max(1,s.length);return{trade:i+1,rollingAvg:Number(avg.toFixed(3))}})}
function streaks(values:number[]){let win=0,loss=0,maxWin=0,maxLoss=0;values.forEach(v=>{if(v>0){win++;loss=0}else if(v<0){loss++;win=0}else{win=0;loss=0}maxWin=Math.max(maxWin,win);maxLoss=Math.max(maxLoss,loss)});return[{name:'Best win streak',count:maxWin},{name:'Worst loss streak',count:maxLoss}]}
function phases(values:number[]){const n=values.length||1;const size=Math.max(1,Math.ceil(n/4));return[0,1,2,3].map(i=>{const s=values.slice(i*size,(i+1)*size);const r=s.reduce((a,b)=>a+b,0);return{name:`Phase ${i+1}`,r:Number(r.toFixed(2)),trades:s.length}})}
function advice(data:any,values:number[]){const avg=Number(data?.avg_R||0),wr=(Number(data?.wins||0)/Math.max(1,values.length))*100;const dd=Math.min(0,...drawdown(values.map((v,i)=>({trade:i+1,equity:values.slice(0,i+1).reduce((a,b)=>a+b,0)}))).map(x=>x.drawdown));if(values.length<30)return 'Sample is still small. Use this as feedback, not proof of an edge.';if(avg>0.15&&wr>35&&dd>-10)return 'Promising profile: positive expectancy, controlled drawdown, and enough winners. Validate on a fresh period before scaling.';if(avg<0)return 'Not ready: expectancy is negative. First reduce weak setups and loss clusters, then retest without changing many rules at once.';return 'Borderline system. Increase sample size, check rolling expectancy, and avoid over-optimizing parameters.'}

export default function Analytics(){
 const[jobs,setJobs]=useState<Job[]>([]),[data,setData]=useState<any>(null),[curve,setCurve]=useState<any[]>([]),[msg,setMsg]=useState('');
 useEffect(()=>{api('/jobs/').then((r:any)=>setJobs(Array.isArray(r)?r:(r.jobs||[]))).catch(e=>setMsg('Cannot reach QuantOS API. Start the backend and refresh. '+e.message))},[]);
 async function load(id:string){if(!id)return;setMsg('Loading analytics...');try{const[r,c]=await Promise.all([api(`/analytics/${id}/r-multiples`),api(`/analytics/${id}/equity-curve`)]);setData(r);setCurve(Array.isArray(c)?c:[]);setMsg('')}catch(e:any){setMsg('Analytics load failed: '+e.message)}}
 const values=(data?.values||[]).map((x:any)=>Number(x)).filter((x:number)=>Number.isFinite(x));
 const wins=Number(data?.wins||0),losses=Number(data?.losses||0),flat=Math.max(0,values.length-wins-losses);
 const pie=[{name:'Wins',value:wins,color:'#22c55e'},{name:'Losses',value:losses,color:'#ef4444'},{name:'Flat',value:flat,color:'#a78bfa'}].filter(x=>x.value>0);
 const equity=curve.length?curve.map((r,i)=>({trade:i+1,equity:Number(r.equity_R||0)})):values.reduce((acc:any[],v:number,i:number)=>{const prev=i?acc[i-1].equity:0;acc.push({trade:i+1,equity:Number((prev+v).toFixed(3))});return acc},[]);
 const dd=drawdown(equity);const dist=bucket(values);const roll=rolling(values);const streak=streaks(values);const phase=phases(values);const maxDD=Math.min(0,...dd.map(x=>x.drawdown));
 return <>
  <div className="hero"><h1>Advanced Analytics</h1><p className="muted">Real backtest analytics: equity, drawdown, R-distribution, rolling expectancy, streaks, sample phases, and action guidance.</p></div>
  {msg&&<div className="card" style={{borderColor:'#7f1d1d',color:msg.startsWith('Cannot')?'#f87171':'#cbd5e1'}}>{msg}</div>}
  <div className="card"><label>Select Job<select onChange={e=>load(e.target.value)} defaultValue=""><option value="">Choose completed job...</option>{jobs.filter(j=>j.status==='completed').map(j=><option key={j.id} value={j.id}>{displayStrategy(j)} · {j.mode} · {parseSymbols(j)} · {j.timeframe||''}</option>)}</select></label></div>
  {data&&<>
   <div className="grid"><Metric label="Gross R" value={`${fmt(data.gross_R)}R`} good={Number(data.gross_R)>=0}/><Metric label="Avg R" value={`${fmt(data.avg_R,3)}R`} good={Number(data.avg_R)>=0}/><Metric label="Max DD" value={`${fmt(maxDD,2)}R`} good={maxDD>-10}/><Metric label="Trades" value={String(values.length)} /></div>
   <div className="card"><h2>QuantOS Advice</h2><p className="muted">{advice(data,values)}</p></div>
   <div className="grid">
    <Chart title="Equity Curve" note="Running cumulative R after each trade."><ResponsiveContainer width="100%" height={240}><AreaChart data={equity}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Area type="monotone" dataKey="equity" stroke="#38bdf8" fill="#38bdf855" strokeWidth={3}/></AreaChart></ResponsiveContainer></Chart>
    <Chart title="Drawdown Curve" note="Distance from previous equity peak."><ResponsiveContainer width="100%" height={240}><AreaChart data={dd}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Area type="monotone" dataKey="drawdown" stroke="#f59e0b" fill="#f59e0b44" strokeWidth={3}/></AreaChart></ResponsiveContainer></Chart>
    <Chart title="Rolling Expectancy" note="Rolling average R over the latest trades."><ResponsiveContainer width="100%" height={240}><LineChart data={roll}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Line type="monotone" dataKey="rollingAvg" stroke="#22c55e" strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer></Chart>
    <Chart title="R Distribution" note="Shows if losses are controlled and winners are meaningful."><ResponsiveContainer width="100%" height={240}><BarChart data={dist}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Bar dataKey="trades" fill="#a78bfa" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></Chart>
    <Chart title="Win/Loss Mix" note="Green wins, red losses, purple flat trades."><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={pie} dataKey="value" nameKey="name" outerRadius={82} label>{pie.map((x,i)=><Cell key={i} fill={x.color}/>)}</Pie><Tooltip contentStyle={tip}/></PieChart></ResponsiveContainer></Chart>
    <Chart title="Phase Performance" note="Splits the sample into four chronological blocks."><ResponsiveContainer width="100%" height={240}><BarChart data={phase}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Bar dataKey="r" fill="#38bdf8" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></Chart>
    <Chart title="Streak Risk" note="Best win streak versus worst loss streak."><ResponsiveContainer width="100%" height={220}><BarChart data={streak}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={tip}/><Bar dataKey="count" fill="#f59e0b" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></Chart>
   </div>
   <div className="card"><h2>Trade Table</h2><p className="muted">Detailed running equity after each trade.</p><div style={{overflowX:'auto'}}><table style={{width:'100%',borderCollapse:'collapse'}}><thead><tr><th style={th}>Trade #</th><th style={th}>Trade ID</th><th style={th}>Equity R</th><th style={th}>Status</th></tr></thead><tbody>{equity.map((r:any,i:number)=><tr key={i}><td style={td}>{i+1}</td><td style={td}>{curve[i]?.trade_id||'-'}</td><td style={td}>{fmt(r.equity,3)}R</td><td style={td}>{Number(r.equity)>=0?'Positive':'Negative'}</td></tr>)}</tbody></table></div></div>
  </>}
 </>}
function Metric({label,value,good}:{label:string;value:string;good?:boolean}){return <div className="card"><h3>{label}</h3><div className="metric" style={{color:good===undefined?'#e2e8f0':good?'#22c55e':'#ef4444'}}>{value}</div></div>}
function Chart({title,note,children}:{title:string;note:string;children:any}){return <div className="card"><h2>{title}</h2><p className="muted">{note}</p>{children}</div>}
