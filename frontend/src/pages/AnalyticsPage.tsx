import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

export const AnalyticsPage: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = async () => {
    setLoading(true);
    setError(null);
    try { setData(await api.getAnalytics()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load analytics'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void loadAnalytics(); }, []);

  if (loading) return <div className="p-8 text-sm text-slate-400">Loading analytics...</div>;
  if (error) return <div role="alert" className="p-8 text-sm text-rose-300">Unable to load analytics: {error} <button onClick={() => void loadAnalytics()} className="ml-2 underline">Retry</button></div>;

  return <div className="p-6 space-y-6">
    <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl"><h2 className="text-xl font-bold text-white">Analytics & Trends</h2><p className="text-xs text-slate-400 mt-1">Counts calculated from persisted security events and alert records.</p></div>
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Metric label="Total events" value={data.total_events} />
      <Metric label="Verified observations" value={data.verified_count} />
      <Metric label="Unverified observations" value={data.unverified_count} />
      <Metric label="Zone violations" value={data.zone_breaches} />
    </div>
    {data.total_events === 0 && <p className="text-sm text-slate-400">No security events recorded. Trends will appear when real events are persisted.</p>}
    <section className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
      <h3 className="text-sm font-bold text-white mb-4">Recorded event observations over the last seven UTC days</h3>
      {data.trends?.length ? <div className="h-72 w-full"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.trends} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}><CartesianGrid stroke="#334155" strokeDasharray="3 3" /><XAxis dataKey="day" stroke="#94a3b8" tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} stroke="#94a3b8" tick={{ fontSize: 11 }} /><Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }} /><Line type="monotone" dataKey="verified" name="Verified" stroke="#34d399" strokeWidth={2} /><Line type="monotone" dataKey="unverified" name="Unknown / unverified" stroke="#fbbf24" strokeWidth={2} /><Line type="monotone" dataKey="breaches" name="Zone violations" stroke="#fb7185" strokeWidth={2} /><Line type="monotone" dataKey="crowd" name="Crowd events" stroke="#60a5fa" strokeWidth={2} /></LineChart></ResponsiveContainer></div> : <p className="text-sm text-slate-400">No trend data available for this period.</p>}
    </section>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <section className="bg-slate-900 border border-slate-800 p-5 rounded-2xl"><h3 className="text-sm font-bold text-white mb-3">Alerts by severity</h3>{data.alerts_by_severity.map((item: any) => <p key={item.severity} className="flex justify-between py-1 text-xs text-slate-300"><span>{item.severity}</span><strong>{item.count}</strong></p>)}</section>
      <section className="bg-slate-900 border border-slate-800 p-5 rounded-2xl"><h3 className="text-sm font-bold text-white mb-3">Alerts by status</h3>{data.alerts_by_status.map((item: any) => <p key={item.status} className="flex justify-between py-1 text-xs text-slate-300"><span>{item.status}</span><strong>{item.count}</strong></p>)}</section>
      <section className="bg-slate-900 border border-slate-800 p-5 rounded-2xl"><h3 className="text-sm font-bold text-white mb-3">Events by camera</h3>{data.events_by_camera.length ? data.events_by_camera.map((item: any) => <p key={item.camera} className="flex justify-between gap-3 py-1 text-xs text-slate-300"><span className="truncate">{item.camera}</span><strong>{item.events}</strong></p>) : <p className="text-xs text-slate-400">No camera records.</p>}</section>
    </div>
  </div>;
};

const Metric: React.FC<{ label: string; value: number }> = ({ label, value }) => <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl"><span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">{label}</span><div className="text-3xl font-bold text-white">{value}</div></div>;
