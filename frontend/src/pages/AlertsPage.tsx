import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Alert } from '../types';
import { formatCampusTimestamp } from '../utils/date';

export const AlertsPage: React.FC<{ focusAlertId?: string | null }> = ({ focusAlertId }) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAlerts();
  }, []);

  useEffect(() => {
    if (!focusAlertId) return;
    window.setTimeout(() => document.getElementById(`security-alert-${focusAlertId}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 0);
  }, [focusAlertId, alerts]);

  const loadAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.getAlerts();
      setAlerts(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load alerts');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (id: string, status: string) => {
    try {
      await api.updateAlertStatus(id, status);
      loadAlerts();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
        <h2 className="text-xl font-bold text-white">Alerts & Security Incident Management</h2>
        <p className="text-xs text-slate-400 mt-1">Real-time Incident Notification Feed & Security Officer Workflow</p>
      </div>

      <div className="space-y-3">
        {error && <p role="alert" className="p-4 text-sm text-rose-300">Unable to load alerts: {error} <button onClick={() => void loadAlerts()} className="ml-2 underline">Retry</button></p>}
        {loading && <p className="p-4 text-sm text-slate-400">Loading alerts...</p>}
        {!loading && !error && alerts.length === 0 && (
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl text-center text-sm text-slate-400">
            No active alerts.
          </div>
        )}
        {!loading && !error && alerts.map((a) => (
          <div id={`security-alert-${a.id}`} key={a.id} className="bg-slate-900 border border-slate-800 p-5 rounded-2xl flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                  a.severity === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800/40' :
                  a.severity === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800/40' :
                  'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                }`}>
                  {a.severity}
                </span>
                <h3 className="text-sm font-bold text-white">{a.title}</h3>
                <span className="text-[10px] text-slate-500 font-mono">
                  {formatCampusTimestamp(a.timestamp)}
                </span>
              </div>
              <p className="text-xs text-slate-400">{a.description}</p>
              <p className="text-xs text-slate-500">
                {[a.event_type, a.member_name, a.track_id != null ? `Track ${a.track_id}` : null, a.camera_name, a.location].filter(Boolean).join(' · ')}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-400 mr-2">Status: {a.status}</span>
              {a.status === 'NEW' && (
                <button
                      onClick={() => void handleUpdateStatus(a.id, 'ACKNOWLEDGED')}
                  className="px-3 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold"
                >
                  Acknowledge
                </button>
              )}
              {a.status !== 'RESOLVED' && a.status !== 'DISMISSED' && (
                <button
                      onClick={() => void handleUpdateStatus(a.id, 'RESOLVED')}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold"
                >
                  Resolve Incident
                </button>
              )}
              {a.status !== 'RESOLVED' && a.status !== 'DISMISSED' && (
                <button
                  onClick={() => void handleUpdateStatus(a.id, 'DISMISSED')}
                  className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-xl text-xs font-semibold"
                >Dismiss</button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
