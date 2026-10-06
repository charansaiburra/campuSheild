import React, { useEffect, useState } from 'react';
import { Settings, Save, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<any[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.getSettings();
      setSettings(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load system settings');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (key: string, value: string) => {
    setError(null);
    try {
      await api.updateSetting(key, value);
      setMsg(`Setting '${key}' updated successfully.`);
      setTimeout(() => setMsg(null), 2500);
      loadSettings();
    } catch (err: any) {
      setError(err instanceof Error ? err.message : 'Unable to update setting');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
        <h2 className="text-xl font-bold text-white">System Settings & Threshold Tuning</h2>
        <p className="text-xs text-slate-400 mt-1">Configure Face Verification Thresholds, Cooldown Durations & Security Rules</p>
      </div>

      {msg && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-800 text-emerald-400 text-xs rounded-xl font-semibold flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>{msg}</span>
        </div>
      )}
      {error && <p role="alert" className="text-sm text-rose-300">{error} <button onClick={() => void loadSettings()} className="ml-2 underline">Retry</button></p>}
      {loading && <p className="text-sm text-slate-400">Loading settings...</p>}
      {!loading && !error && settings.length === 0 && <p className="text-sm text-slate-400">No settings are configured.</p>}

      <div className="space-y-4">
        {!loading && !error && settings.map((s) => (
          <div key={s.key} className="bg-slate-900 border border-slate-800 p-5 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-white font-mono">{s.key}</h3>
              <p className="text-xs text-slate-400 mt-0.5">{s.description}</p>
            </div>
            <div className="flex items-center gap-2">
              <input
                type="text"
                defaultValue={s.value}
                onBlur={(e) => handleUpdate(s.key, e.target.value)}
                className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white font-mono"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
