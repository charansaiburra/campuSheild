import React, { useEffect, useState } from 'react';
import { AlertTriangle, Search, Filter, Image as ImageIcon } from 'lucide-react';
import { api } from '../services/api';
import { SecurityEvent } from '../types';
import { formatCampusTimestamp } from '../utils/date';

export const EventsPage: React.FC = () => {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [severityFilter, setSeverityFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [selectedSnapshot, setSelectedSnapshot] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadEvents();
  }, [severityFilter, typeFilter]);

  const loadEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      let query = '?';
      if (severityFilter) query += `severity=${severityFilter}&`;
      if (typeFilter) query += `event_type=${typeFilter}&`;
      const list = await api.getEvents(query);
      setEvents(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load security events');
    } finally {
      setLoading(false);
    }
  };

  const openSnapshot = async (eventId: string) => {
    try {
      const blob = await api.downloadEventSnapshot(eventId);
      setSelectedSnapshot(URL.createObjectURL(blob));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load event snapshot');
    }
  };

  useEffect(() => () => { if (selectedSnapshot) URL.revokeObjectURL(selectedSnapshot); }, [selectedSnapshot]);

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-5 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white">Security Events Audit Log</h2>
          <p className="text-xs text-slate-400 mt-1">Real-time Verified/Unverified Detections, Zone Breaches & Crowd Events</p>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-3">
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-semibold text-white"
          >
            <option value="">All Severities</option>
            <option value="INFO">INFO</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>

          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-semibold text-white"
          >
            <option value="">All Event Types</option>
            <option value="PERSON_VERIFIED">PERSON VERIFIED</option>
            <option value="UNKNOWN_PERSON">UNKNOWN PERSON</option>
            <option value="PERSON_UNVERIFIED">PERSON UNVERIFIED</option>
            <option value="UNAUTHORIZED_ZONE_ACCESS">UNAUTHORIZED ZONE ACCESS</option>
            <option value="CROWD_THRESHOLD_EXCEEDED">CROWD THRESHOLD EXCEEDED</option>
            <option value="CAMERA_ONLINE">CAMERA ONLINE</option>
            <option value="CAMERA_OFFLINE">CAMERA OFFLINE</option>
          </select>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        {error && <p role="alert" className="p-4 text-sm text-rose-300">Unable to load security events: {error} <button onClick={() => void loadEvents()} className="ml-2 underline">Retry</button></p>}
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
              <th className="py-3.5 px-4">Timestamp</th>
              <th className="py-3.5 px-4">Event Type</th>
              <th className="py-3.5 px-4">Subject</th>
              <th className="py-3.5 px-4">Location</th>
              <th className="py-3.5 px-4">Severity</th>
              <th className="py-3.5 px-4">Snapshot</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {loading ? (
              <tr><td colSpan={6} className="py-8 text-center text-slate-500">Loading events...</td></tr>
            ) : !error && events.length === 0 ? (
              <tr><td colSpan={6} className="py-8 text-center text-slate-500">No security events recorded.</td></tr>
            ) : null}
            {!loading && !error && events.map((e) => (
              <tr key={e.id} className="hover:bg-slate-800/40 transition">
                <td className="py-3.5 px-4 font-mono text-slate-400">
                  {formatCampusTimestamp(e.timestamp)}
                </td>
                <td className="py-3.5 px-4 font-bold text-white">
                  {e.event_type.replace(/_/g, ' ')}
                </td>
                <td className="py-3.5 px-4">{e.member_name || 'Unknown person'}</td>
                <td className="py-3.5 px-4">{e.location || '—'}</td>
                <td className="py-3.5 px-4">
                  <span className={`px-2 py-0.5 rounded-full font-bold text-[10px] ${
                    e.severity === 'HIGH' ? 'bg-rose-950 text-rose-400 border border-rose-800/40' :
                    e.severity === 'MEDIUM' ? 'bg-amber-950 text-amber-400 border border-amber-800/40' :
                    'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                  }`}>
                    {e.severity}
                  </span>
                </td>
                <td className="py-3.5 px-4">
                  {e.snapshot_path ? (
                    <button
                      onClick={() => void openSnapshot(e.id)}
                      className="p-1.5 bg-slate-800 hover:bg-slate-700 text-indigo-400 rounded-lg transition"
                      title="View Frame Snapshot"
                    >
                      <ImageIcon className="w-4 h-4" />
                    </button>
                  ) : (
                    <span className="text-slate-600">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Snapshot Preview Modal */}
      {selectedSnapshot && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 max-w-2xl w-full space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-white uppercase tracking-wider">Event Frame Snapshot</h4>
              <button onClick={() => { if (selectedSnapshot) URL.revokeObjectURL(selectedSnapshot); setSelectedSnapshot(null); }} className="text-xs text-slate-400 hover:text-white">
                Close
              </button>
            </div>
            <img src={selectedSnapshot} alt="Snapshot" className="w-full rounded-xl object-contain max-h-[450px]" />
          </div>
        </div>
      )}
    </div>
  );
};
