'use client';
import { useEffect, useMemo, useState } from 'react';
import { api } from '../../lib/api';
import {
  Area, AreaChart, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Pie, PieChart
} from 'recharts';

interface Job { id: string; status: string; mode: string; created_at: string; display_strategy_id?: string; user_strategy_id?: string; strategy_code?: string; strategy_id?: string; symbols_json?: string; timeframe?: string; }

function fmt(n:any,d=2){const x=Number(n??0); return Number.isFinite(x)?x.toFixed(d).replace(/\.00$/,''):'0'}
function displayStrategy(j: Job) { return j.display_strategy_id || j.user_strategy_id || j.strategy_code || j.strategy_id || 'STRATEGY'; }
function coachJobLabel(j: Job) { const date = j.created_at ? new Date(j.created_at).toLocaleString(undefined, { hour12: false }) : 'date unknown'; return `${displayStrategy(j)} · ${(j.mode || 'job').toUpperCase()} · ${j.status} · ${date}`; }
function bucketR(trades:number[]){const rows=[{name:'Big Loss',trades:0},{name:'Small Loss',trades:0},{name:'Flat',trades:0},{name:'Good Win',trades:0},{name:'Big Win',trades:0}]; trades.forEach(r=>{if(r<=-1)rows[0].trades++; else if(r<0)rows[1].trades++; else if(r<0.5)rows[2].trades++; else if(r<2)rows[3].trades++; else rows[4].trades++;}); return rows;}
function drawdownCurve(curve:number[]){let peak=curve[0]||0; return curve.map((v,i)=>{peak=Math.max(peak,v); return {trade:i+1,drawdown:Number((v-peak).toFixed(3))}})}
function coachNarrative(report:any,m:any){const avg=Number(m.avg_R||0), dd=Number(m.max_drawdown_R||0), wr=Number(m.win_rate||0)*100, pf=Number(m.profit_factor||0); if(avg<0||pf<1){return `Your current strategy is not ready to scale. Expectancy is ${fmt(avg,3)}R/trade, win rate is ${fmt(wr,1)}%, and max drawdown reached ${fmt(dd)}R. Focus on reducing weak entries, avoiding loss clusters, and retesting only after rule changes are controlled.`} if(avg>0.15&&pf>1.2){return `This strategy shows a promising paper-trading edge. Expectancy is ${fmt(avg,3)}R/trade with profit factor ${fmt(pf)}. Validate across more regimes and avoid changing too many parameters at once.`} return `This strategy is borderline. The best next step is more sample size and walk-forward testing, not aggressive optimization.`}

function MetricCard({label,value,sub,accent}:{label:string;value:any;sub?:string;accent?:string}){return <div style={{background:'#111827',border:'1px solid #334155',borderRadius:14,padding:'20px 24px'}}><div style={{fontSize:11,color:'#94a3b8',textTransform:'uppercase',letterSpacing:1,marginBottom:8}}>{label}</div><div style={{fontSize:30,fontWeight:900,color:accent||'#e2e8f0'}}>{value}</div>{sub&&<div style={{fontSize:12,color:'#94a3b8',marginTop:6}}>{sub}</div>}</div>}
function InsightList({title,items,accent}:{title:string;items?:string[];accent?:string}){return <div style={{background:'#111827',border:'1px solid #334155',borderRadius:14,padding:22}}><h3 style={{marginTop:0}}>{title}</h3>{items?.length?items.map((x,i)=><div key={i} style={{padding:'9px 0',borderBottom:'1px solid #1e293b',color:accent||'#cbd5e1',lineHeight:1.5}}>• {x}</div>):<p style={{color:'#94a3b8'}}>No items available yet.</p>}</div>}

export default function QuantCoach() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [report, setReport] = useState<any>(null);
  const [msg, setMsg] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => { api('/jobs/').then((r:any) => { setJobs(Array.isArray(r) ? r : (r.jobs || [])); setMsg(''); }).catch(e => setMsg('Cannot reach QuantOS API. Start the backend and refresh. Details: ' + e.message)); }, []);
  async function load(id: string) { if (!id) return; setMsg(''); setReport(null); setLoading(true); try { const r = await api(`/coach/${id}/coach-report`); setReport(r); } catch (e: any) { setMsg(e.message); } finally { setLoading(false); } }

  const m = report?.metrics || {};
  const mc = report?.monte_carlo || {};
  const fit = report?.lifestyle_fit || {};
  const discipline = report?.rule_discipline || {};
  const stress = report?.stress_testing || {};
  const wf = report?.walk_forward_analysis || {};
  const curve:number[] = Array.isArray(m.equity_curve_R) ? m.equity_curve_R.map((x:any)=>Number(x||0)) : [];
  const allR:number[] = curve.map((v,i)=>(i===0?v:v-curve[i-1]));
  const hasCoachData = Number(m.trades || report?.summary?.total_trades || 0) > 0;
  const equityData = curve.map((v,i)=>({trade:i+1,equity:Number(v.toFixed(3))}));
  const ddData = useMemo(()=>drawdownCurve(curve),[report]);
  const rDist = useMemo(()=>bucketR(allR),[report]);
  const winLoss = [
    {name:'Wins',value:Math.round(Number(m.win_rate||0)*Number(m.trades||0))},
    {name:'Losses',value:Math.max(0,Number(m.trades||0)-Math.round(Number(m.win_rate||0)*Number(m.trades||0)))}
  ].filter(x=>x.value>0);
  const stability = [
    {name:'Walk Forward',score:Math.round(Number(wf.pass_rate||0)*100)},
    {name:'Stress Test',score:Math.round(Number(stress.pass_rate||0)*100)},
    {name:'Positive MC',score:Math.round(Number(mc.probability_final_R_positive||0)*100)},
    {name:'Lifestyle',score:Number(fit.score||0)},
  ];
  const verdictColor:Record<string,string>={PROMISING_PAPER_SYSTEM:'#22c55e',NEEDS_MORE_DATA:'#f59e0b',DO_NOT_SCALE_YET:'#ef4444'};

  const s={page:{background:'#0d0d1a',minHeight:'100vh',padding:24,fontFamily:'system-ui,sans-serif',color:'#e2e8f0'},hero:{marginBottom:28},h1:{fontSize:30,fontWeight:900,margin:0,background:'linear-gradient(135deg,#6366f1,#8b5cf6)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'},sub:{color:'#bad4ff',marginTop:8,fontSize:14,lineHeight:1.6},card:{background:'#111827',border:'1px solid #334155',borderRadius:16,padding:24,marginBottom:20},cardTitle:{fontSize:13,color:'#c4b5fd',textTransform:'uppercase' as const,letterSpacing:1,marginBottom:16,fontWeight:800},grid2:{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(390px,1fr))',gap:18,marginBottom:20},grid3:{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))',gap:18,marginBottom:20},danger:{background:'#2a1a1a',border:'1px solid #ef444433',borderRadius:8,padding:'12px 16px',color:'#fca5a5',marginBottom:16},select:{width:'100%',background:'#0d0d1a',color:'#e2e8f0',border:'1px solid #475569',borderRadius:10,padding:'12px 14px',fontSize:14},disclaimer:{color:'#94a3b8',fontSize:11,textAlign:'center' as const,padding:'16px 0',marginTop:24,borderTop:'1px solid #334155'}};

  return <div style={s.page}>
    <div style={s.hero}><h1 style={s.h1}>Quant Coach</h1><p style={s.sub}>One real-data coach report for completed QuantOS backtests and paper-trading sessions. It combines expectancy, drawdown, R-distribution, Monte Carlo, discipline, walk-forward stability, stress testing, and clear visual advice.</p></div>
    {msg&&<div style={s.danger}>{msg}</div>}
    <div style={s.card}><div style={s.cardTitle}>Select Completed Job</div><select style={s.select} onChange={e=>load(e.target.value)} defaultValue=""><option value="">Choose a completed backtest or paper job…</option>{jobs.filter(j=>j.status==='completed').map(j=><option key={j.id} value={j.id}>{coachJobLabel(j)}</option>)}</select>{loading&&<div style={{marginTop:12,color:'#a78bfa'}}>Generating report…</div>}</div>
    {report&&!hasCoachData&&<div style={s.card}><div style={s.cardTitle}>Coach Status</div><h2 style={{marginTop:0,color:'#f59e0b'}}>Waiting for completed trades</h2><p style={{color:'#cbd5e1',lineHeight:1.6}}>This report has no closed trades yet. Run a backtest/live paper session until trades close, then reopen this report.</p></div>}
    {report&&hasCoachData&&<>
      <div style={s.grid3}>
        <div style={{background:(verdictColor[report.final_verdict]||'#6366f1')+'18',border:`2px solid ${(verdictColor[report.final_verdict]||'#6366f1')}77`,borderRadius:14,padding:'20px 24px'}}><div style={{fontSize:11,color:'#cbd5e1',textTransform:'uppercase',letterSpacing:1,marginBottom:8}}>Verdict</div><div style={{fontSize:22,fontWeight:900,color:verdictColor[report.final_verdict]||'#a78bfa'}}>{report.final_verdict||'NO_DATA'}</div></div>
        <MetricCard label="Expectancy" value={`${fmt(m.avg_R,3)}R`} sub={`per trade · ${m.trades??0} trades`} accent={(m.avg_R||0)>0?'#22c55e':'#ef4444'} />
        <MetricCard label="Max Drawdown" value={`${fmt(m.max_drawdown_R)}R`} sub="worst observed" accent="#f59e0b" />
      </div>
      <div style={s.card}><div style={s.cardTitle}>QuantOS Coach Advice</div><p style={{color:'#dbeafe',fontSize:16,lineHeight:1.75,margin:0}}>{coachNarrative(report,m)}</p></div>
      <div style={s.grid2}>
        <div style={s.card}><div style={s.cardTitle}>Equity Curve</div><ResponsiveContainer width="100%" height={260}><AreaChart data={equityData}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Area type="monotone" dataKey="equity" stroke="#38bdf8" fill="#38bdf855" strokeWidth={3}/></AreaChart></ResponsiveContainer></div>
        <div style={s.card}><div style={s.cardTitle}>Drawdown Curve</div><ResponsiveContainer width="100%" height={260}><AreaChart data={ddData}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="trade" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Area type="monotone" dataKey="drawdown" stroke="#f59e0b" fill="#f59e0b44" strokeWidth={3}/></AreaChart></ResponsiveContainer></div>
        <div style={s.card}><div style={s.cardTitle}>R-Multiple Distribution</div><ResponsiveContainer width="100%" height={260}><BarChart data={rDist}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1"/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Bar dataKey="trades" fill="#a78bfa" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></div>
        <div style={s.card}><div style={s.cardTitle}>Win/Loss Mix</div><ResponsiveContainer width="100%" height={260}><PieChart><Pie data={winLoss} dataKey="value" nameKey="name" outerRadius={92} label>{winLoss.map((_,i)=><Cell key={i} fill={i===0?'#22c55e':'#ef4444'}/>)}</Pie><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/></PieChart></ResponsiveContainer></div>
        <div style={s.card}><div style={s.cardTitle}>Robustness Scores</div><ResponsiveContainer width="100%" height={260}><BarChart data={stability}><CartesianGrid strokeDasharray="3 3" stroke="#334155"/><XAxis dataKey="name" stroke="#cbd5e1" tick={{fontSize:11}}/><YAxis stroke="#cbd5e1"/><Tooltip contentStyle={{background:'#111827',border:'1px solid #475569',color:'#e2e8f0'}}/><Bar dataKey="score" fill="#22c55e" radius={[8,8,0,0]}/></BarChart></ResponsiveContainer></div>
        <div style={s.card}><div style={s.cardTitle}>Monte Carlo Risk</div><div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(130px,1fr))',gap:12}}>{[{label:'Median',val:mc.final_R?.p50,accent:'#22c55e'},{label:'Bad Case',val:mc.final_R?.p05,accent:'#ef4444'},{label:'DD p95',val:mc.drawdown_R?.p95?`${mc.drawdown_R.p95}R`:'—',accent:'#f59e0b'},{label:'Risk Ruin',val:mc.risk_of_ruin_minus_10R!=null?`${(mc.risk_of_ruin_minus_10R*100).toFixed(1)}%`:'—',accent:'#ef4444'}].map(x=><div key={x.label} style={{background:'#0d0d1a',border:'1px solid #334155',borderRadius:10,padding:14}}><div style={{fontSize:11,color:'#94a3b8'}}>{x.label}</div><div style={{fontSize:22,fontWeight:900,color:x.accent}}>{x.val??'—'}</div></div>)}</div></div>
      </div>
      <div style={s.grid2}><InsightList title="Coach Insights" items={report.coach_insights} /><InsightList title="Next Actions" items={report.next_actions} accent="#a78bfa" /></div>
      <div style={s.grid2}><InsightList title="Rule Discipline" items={[`Manual violations: ${discipline.manual_rule_violations_detected??0}`,`R impact: ${discipline.manual_rule_violation_R_impact??0}R`,`Tracking status: ${discipline.status||'unknown'}`]} /><InsightList title="Lifestyle Fit" items={[`Score: ${fit.score??'—'}/100`,`Label: ${fit.label||'—'}`,`Monitoring burden: ${fit.monitoring_burden||'—'}`,`Psychological burden: ${fit.psychological_burden||'—'}`]} /></div>
    </>}
    <div style={s.disclaimer}>QuantOS Quant Coach is research/analytics only. Paper trading and backtests are hypothetical. Not financial advice.</div>
  </div>;
}
