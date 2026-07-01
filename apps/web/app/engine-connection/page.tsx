'use client';
import {useEffect,useState} from 'react';
import {api,formatApiError} from '../../lib/api';

export default function EngineConnection(){
  const [status,setStatus]=useState<any>(null);
  const [token,setToken]=useState<any>(null);
  const [msg,setMsg]=useState('');
  async function refresh(){try{setStatus(await api('/engine/status'));}catch(e){setMsg(formatApiError(e));}}
  async function connect(source='BTCUSDT'){try{setMsg(''); const r=await api('/engine/token',{method:'POST',body:JSON.stringify({mode:'paper',exchange:'binance',source})}); setToken(r); await refresh();}catch(e){setMsg(formatApiError(e));}}
  useEffect(()=>{refresh(); const t=window.setInterval(refresh,3000); return()=>window.clearInterval(t);},[]);
  const latency=status?.latency||{};
  async function copyCommand(cmd?: string){ if(cmd && navigator?.clipboard) await navigator.clipboard.writeText(cmd); }
  return <>
    <div className="hero"><h1>Engine Connection</h1><p>Run market data, paper simulation, and low-latency work on your machine. Cloud stores only safe telemetry/results.</p></div>
    {msg&&<div className="card" style={{color:'#fca5a5'}}>{msg}</div>}
    <div className="card"><h2>Local Engine Bridge</h2><button onClick={()=>connect('BTCUSDT')}>Connect Local Engine</button>{' '}<button onClick={()=>connect('BTCUSDT')}>Connect BTC Live Feed</button>{' '}<button onClick={()=>connect('CUSTOM')}>Connect Custom Source</button>
      {token&&<div style={{marginTop:16}}><b>Run this locally on Windows:</b><pre style={{whiteSpace:'pre-wrap'}}>{token.windows_command || token.command}</pre><button onClick={()=>copyCommand(token.windows_command || token.command)}>Copy Windows command</button><div style={{marginTop:14}}><b>Run this locally on Linux/macOS/Docker:</b><pre style={{whiteSpace:'pre-wrap'}}>{token.linux_command || './build/quantos-engine --token <TOKEN> --mode paper --exchange binance --symbol BTCUSDT'}</pre><button onClick={()=>copyCommand(token.linux_command)}>Copy Linux command</button></div><p style={{color:'#94a3b8'}}>Token expires at epoch {token.expires_at_epoch}. Do not paste exchange API keys into QuantOS cloud.</p></div>}
    </div>
    <div className="card"><h2>Status</h2><div className="grid">
      <div><b>Connected/Disconnected</b><div className="metric">{status?.connected?'BTCUSDT connected':'Disconnected'}</div></div><div><b>Engine token status</b><div className="metric">{token?'Generated':'Not generated'}</div></div>
      <div><b>Exchange/source</b><div className="metric">{status?.exchange||'—'} / {status?.source||'—'}</div></div>
      <div><b>Mode</b><div className="metric">{status?.mode||'paper'}</div></div>
      <div><b>Last heartbeat</b><div className="metric">{status?.last_heartbeat||'—'}</div></div>
      <div><b>Engine version</b><div className="metric">{status?.engine_version||'—'}</div></div>
      <div><b>BTCUSDT latest</b><div className="metric">{status?.latest_price||'—'}</div></div><div><b>Paper session</b><div className="metric">{status?.connected?'local paper ready':'waiting for local engine'}</div></div><div><b>P&L / position / trades</b><div className="metric">{status?.payload?'synced':'—'}</div></div>
      <div><b>p50/p95/p99 internal latency</b><div className="metric">{latency.p50_us||0}/{latency.p95_us||0}/{latency.p99_us||0} µs</div></div>
    </div><p style={{color:'#fbbf24'}}>Paper trading only. Real-money trading is disabled.</p></div>
  </>;
}
