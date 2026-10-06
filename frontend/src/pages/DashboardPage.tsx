import React, { useEffect, useState } from 'react';
import { Camera, Users, ShieldCheck, UserX, AlertTriangle, Bell, ArrowUpRight, Video } from 'lucide-react';
import { api } from '../services/api';
import { formatCampusTimestamp } from '../utils/date';

interface DashboardPageProps {
  onNavigate: (tab: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSummary();
  }, []);

  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboardSummary();
      setData(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-slate-400 text-sm">Loading security metrics...</div>;
  }

  if (error) {
    return <div role="alert" className="p-8 text-rose-300 text-sm">Unable to load dashboard: {error} <button onClick={() => void loadSummary()} className="ml-2 underline">Retry</button></div>;
  }

  const cards = data?.cards || {};
  const recentEvents = data?.recent_events || [];

  return (
    <div className="p-6 space-y-6">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-6 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white tracking-wide">Campus Security Command Center</h2>
          <p className="text-xs text-slate-400 mt-1">Real-time CCTV AI Monitoring, Person Detection & Zone Authorization</p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => onNavigate('live-monitoring')}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition"
          >
            <Video className="w-4 h-4" />
            <span>Launch Live Monitoring</span>
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Cameras</span>
            <div className="p-2 bg-indigo-950/60 text-indigo-400 rounded-xl border border-indigo-800/40">
              <Camera className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-white">{cards.total_cameras || 0}</div>
          <p className="text-[11px] text-emerald-400 font-medium mt-1">{cards.online_cameras || 0} Online Streams</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Verified Observations</span>
            <div className="p-2 bg-emerald-950/60 text-emerald-400 rounded-xl border border-emerald-800/40">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-emerald-400">{cards.verified_persons || 0}</div>
          <p className="text-[11px] text-slate-400 font-medium mt-1">Students / Faculty Authenticated</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Unverified Observations</span>
            <div className="p-2 bg-amber-950/60 text-amber-400 rounded-xl border border-amber-800/40">
              <UserX className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-amber-400">{cards.unverified_persons || 0}</div>
          <p className="text-[11px] text-slate-400 font-medium mt-1">Unknown / Unregistered Subjects</p>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Active Alerts</span>
            <div className="p-2 bg-rose-950/60 text-rose-400 rounded-xl border border-rose-800/40">
              <Bell className="w-5 h-5" />
            </div>
          </div>
          <div className="text-2xl font-bold text-rose-400">{cards.active_alerts || 0}</div>
          <p className="text-[11px] text-slate-400 font-medium mt-1">Requires Security Attention</p>
        </div>
      </div>

      {/* Security Event Feed */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-bold text-white tracking-wide">Recent Security Audit Trail</h3>
          <button
            onClick={() => onNavigate('events')}
            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
          >
            <span>View All Events</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="text-slate-400 border-b border-slate-800 font-semibold">
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4">Event Type</th>
                <th className="py-3 px-4">Subject</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {recentEvents.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">No security events recorded yet.</td>
                </tr>
              ) : (
                recentEvents.map((evt: any) => (
                  <tr key={evt.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 font-mono text-slate-400">
                      {formatCampusTimestamp(evt.timestamp)}
                    </td>
                    <td className="py-3 px-4 font-semibold text-white">
                      {evt.event_type.replace(/_/g, ' ')}
                    </td>
                    <td className="py-3 px-4">
                      {evt.member_name || 'Unknown person'}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                        evt.severity === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800/40' :
                        evt.severity === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800/40' :
                        'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                      }`}>
                        {evt.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-slate-400 font-medium">{evt.status}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
