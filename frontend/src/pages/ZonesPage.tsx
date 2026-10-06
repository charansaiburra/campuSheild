import React, { useEffect, useState } from 'react';
import { Plus, Trash2, ShieldAlert, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { RestrictedZone, Camera } from '../types';

const roleOptions = ['STUDENT', 'FACULTY', 'TEACHING_STAFF', 'NON_TEACHING_STAFF', 'SECURITY_STAFF', 'AUTHORIZED_VISITOR'];

export const ZonesPage: React.FC = () => {
  const [zones, setZones] = useState<RestrictedZone[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [frameError, setFrameError] = useState<string | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [frameSize, setFrameSize] = useState<[number, number] | null>(null);
  const [points, setPoints] = useState<number[][]>([]);
  const [name, setName] = useState('');
  const [cameraId, setCameraId] = useState('');
  const [occupancyThreshold, setOccupancyThreshold] = useState(5);
  const [allowedRoles, setAllowedRoles] = useState<string[]>(['FACULTY', 'SECURITY_STAFF']);
  const [saving, setSaving] = useState(false);

  useEffect(() => { void loadData(); }, []);
  useEffect(() => () => { if (frameUrl) URL.revokeObjectURL(frameUrl); }, [frameUrl]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [zoneList, cameraList] = await Promise.all([api.getZones(), api.getCameras()]);
      setZones(zoneList);
      setCameras(cameraList);
      setCameraId(current => current || cameraList[0]?.id || '');
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load zones and cameras');
    } finally {
      setLoading(false);
    }
  };

  const openCreate = () => {
    const selected = cameraId || cameras[0]?.id || '';
    setCameraId(selected);
    setPoints([]);
    setName('');
    setSaveError(null);
    setFrameError(null);
    setFrameSize(null);
    setShowModal(true);
    if (selected) void loadFrame(selected);
  };

  const loadFrame = async (id: string) => {
    setFrameError(null);
    setPoints([]);
    setFrameSize(null);
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    setFrameUrl(null);
    try {
      const blob = await api.getCameraSnapshot(id);
      setFrameUrl(URL.createObjectURL(blob));
    } catch (reason) {
      setFrameError(reason instanceof Error ? reason.message : 'Unable to capture a real camera frame');
    }
  };

  const addPoint = (event: React.MouseEvent<HTMLImageElement>) => {
    if (!frameSize) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = Math.round((event.clientX - rect.left) * frameSize[0] / rect.width);
    const y = Math.round((event.clientY - rect.top) * frameSize[1] / rect.height);
    setPoints(current => [...current, [x, y]]);
  };

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaveError(null);
    if (!cameraId || points.length < 3 || allowedRoles.length === 0) {
      setSaveError('Select a camera, draw at least three polygon points, and choose an allowed role.');
      return;
    }
    setSaving(true);
    try {
      await api.createZone({ camera_id: cameraId, name, polygon: points, allowed_roles: allowedRoles, occupancy_threshold: occupancyThreshold });
      setShowModal(false);
      setFrameUrl(null);
      await loadData();
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : 'Unable to create zone');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this restricted zone?')) return;
    try {
      await api.deleteZone(id);
      await loadData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to delete zone');
    }
  };

  const setActive = async (zone: RestrictedZone, isActive: boolean) => {
    try {
      await api.updateZone(zone.id, { is_active: isActive });
      await loadData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update zone');
    }
  };

  return <div className="p-6 space-y-6">
    <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-5 rounded-2xl">
      <div><h2 className="text-xl font-bold text-white">Restricted Zones</h2><p className="text-xs text-slate-400 mt-1">Draw polygons on a captured frame from the selected camera.</p></div>
      <div className="flex gap-2"><button onClick={() => void loadData()} aria-label="Refresh zones" className="p-2 bg-slate-800 text-slate-300 rounded-xl"><RefreshCw className="w-4 h-4" /></button><button onClick={openCreate} disabled={cameras.length === 0} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 disabled:opacity-40 text-white text-xs rounded-xl"><Plus className="w-4 h-4" />Define Zone</button></div>
    </div>
    {error && <p role="alert" className="text-sm text-rose-300">Unable to load restricted zones: {error}</p>}
    {loading ? <p className="text-sm text-slate-400">Loading zones...</p> : !error && zones.length === 0 ? <p className="bg-slate-900 border border-slate-800 p-8 rounded-2xl text-center text-sm text-slate-400">No data available</p> : null}
    {!loading && !error && <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{zones.map(zone => <div key={zone.id} className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3">
      <div className="flex items-center justify-between"><div className="flex items-center gap-2"><ShieldAlert className="w-5 h-5 text-rose-400" /><h3 className="text-base font-bold text-white">{zone.name}</h3></div><button onClick={() => void handleDelete(zone.id)} aria-label={`Delete ${zone.name}`} className="p-1.5 text-rose-400"><Trash2 className="w-4 h-4" /></button></div>
      <p className="text-xs text-slate-400">Camera: {cameras.find(camera => camera.id === zone.camera_id)?.name || 'Camera unavailable'} · {zone.is_active ? 'Active' : 'Inactive'}</p>
      <p className="text-xs text-slate-400">Occupancy threshold: {zone.occupancy_threshold} · Polygon points: {zone.polygon.length}</p>
      <div className="flex flex-wrap gap-1.5">{zone.allowed_roles.map(role => <span key={role} className="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 text-[10px] font-bold">{role}</span>)}</div>
      <button onClick={() => void setActive(zone, !zone.is_active)} className="px-3 py-1.5 bg-slate-800 text-slate-200 rounded-lg text-xs">{zone.is_active ? 'Deactivate zone' : 'Activate zone'}</button>
    </div>)}</div>}

    {showModal && <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 overflow-y-auto"><div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-3xl space-y-4 my-8">
      <h3 className="text-lg font-bold text-white">Draw restricted zone</h3>
      <form onSubmit={handleCreate} className="space-y-4 text-xs">
        <div className="grid sm:grid-cols-2 gap-3"><label className="text-slate-300">Zone name<input value={name} onChange={e => setName(e.target.value)} className="mt-1 w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white" required /></label><label className="text-slate-300">Camera<select value={cameraId} onChange={e => { setCameraId(e.target.value); void loadFrame(e.target.value); }} className="mt-1 w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white">{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name} ({camera.location})</option>)}</select></label></div>
        {frameError && <p role="alert" className="text-rose-300">Unable to capture camera frame: {frameError}</p>}
        {frameUrl && <div><p className="mb-2 text-slate-300">Click the camera frame to add polygon vertices. Points: {points.length} <button type="button" onClick={() => setPoints([])} className="ml-2 underline text-indigo-300">Clear points</button></p><div className="flex justify-center overflow-auto bg-black rounded-xl"><div className="relative w-fit"><img src={frameUrl} alt="Real camera frame for zone drawing" className="block max-h-[450px] max-w-full w-auto cursor-crosshair" onLoad={event => setFrameSize([event.currentTarget.naturalWidth, event.currentTarget.naturalHeight])} onClick={addPoint} /><svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox={frameSize ? `0 0 ${frameSize[0]} ${frameSize[1]}` : undefined} preserveAspectRatio="none">{points.length > 1 && <polyline points={points.map(point => point.join(',')).join(' ')} fill="rgba(99,102,241,0.2)" stroke="#818cf8" strokeWidth={Math.max(2, (frameSize?.[0] || 800) / 300)} />}{points.map((point, index) => <circle key={index} cx={point[0]} cy={point[1]} r={Math.max(4, (frameSize?.[0] || 800) / 150)} fill="#f43f5e" />)}</svg></div></div></div>}
        {!frameUrl && !frameError && <p className="text-slate-400">Capturing a frame from the configured camera...</p>}
        <label className="block text-slate-300">Occupancy threshold<input type="number" min={1} value={occupancyThreshold} onChange={e => setOccupancyThreshold(Number(e.target.value))} className="mt-1 w-32 p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white" required /></label>
        <fieldset><legend className="text-slate-300 mb-2">Allowed roles</legend><div className="flex flex-wrap gap-3">{roleOptions.map(role => <label key={role} className="flex items-center gap-1.5 text-slate-300"><input type="checkbox" checked={allowedRoles.includes(role)} onChange={event => setAllowedRoles(current => event.target.checked ? [...current, role] : current.filter(item => item !== role))} />{role}</label>)}</div></fieldset>
        {saveError && <p role="alert" className="text-rose-300">{saveError}</p>}
        <div className="flex justify-end gap-3"><button type="button" onClick={() => { setShowModal(false); if (frameUrl) URL.revokeObjectURL(frameUrl); setFrameUrl(null); }} className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl">Cancel</button><button disabled={saving || points.length < 3 || !frameSize} type="submit" className="px-4 py-2 bg-indigo-600 disabled:opacity-40 text-white rounded-xl">{saving ? 'Saving...' : 'Save zone'}</button></div>
      </form>
    </div></div>}
  </div>;
};
