import React, { useEffect, useRef, useState } from 'react';
import { Camera as CameraIcon, ShieldCheck, UserX, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { Camera } from '../types';

export const LiveMonitoringPage: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  const [telemetry, setTelemetry] = useState<any>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraLoading, setCameraLoading] = useState(true);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [recentEventsError, setRecentEventsError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);
  const [monitoring, setMonitoring] = useState(false);
  const [stopping, setStopping] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);

  const loadCameras = async () => {
    setCameraLoading(true);
    setCameraError(null);
    try {
      const list = await api.getMonitoringCameras();
      setCameras(list);
      setSelectedCamera(current => list.find((camera: Camera) => camera.id === current?.id) || list[0] || null);
    } catch (error) {
      setCameraError(error instanceof Error ? error.message : 'Unable to load cameras');
    } finally {
      setCameraLoading(false);
    }
  };

  useEffect(() => { void loadCameras(); }, []);

  useEffect(() => {
    setTelemetry(null);
    setStreamError(null);
    setRecentEvents([]);
    setRecentEventsError(null);
    if (!selectedCamera) return;
    let active = true;
    void api.getEvents(`?camera_id=${encodeURIComponent(selectedCamera.id)}&limit=8`).then(events => {
      if (active) setRecentEvents(events);
    }).catch(reason => {
      if (active) setRecentEventsError(reason instanceof Error ? reason.message : 'Unable to load persisted camera events');
    });
    return () => { active = false; };
  }, [selectedCamera?.id]);

  useEffect(() => {
    if (!monitoring || !selectedCamera) {
      setTelemetry(null);
      return;
    }
    setStreamError(null);
    const scheme = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('access_token');
    if (!token) { setStreamError('Your session has expired. Sign in again to monitor cameras.'); setMonitoring(false); return; }
    const socket = new WebSocket(`${scheme}//${window.location.host}/api/v1/monitoring/ws/${selectedCamera.id}`, ['campus-security', `bearer.${token}`]);
    socketRef.current = socket;
    socket.onmessage = event => {
      if (socketRef.current !== socket) return;
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'stopped') {
          setStopping(false);
          setMonitoring(false);
          setTelemetry(null);
          return;
        }
        if (message.type === 'error') {
          setStreamError(`${message.code}: ${message.message}`);
          setTelemetry(null);
          setMonitoring(false);
          return;
        }
        const data = message.data || message;
        if (data.camera_id !== selectedCamera.id || !data.frame?.startsWith('data:image/jpeg;base64,') || !data.summary || !Array.isArray(data.detections)) {
          throw new Error('Backend sent malformed live telemetry for the selected camera');
        }
        setStreamError(null);
        setTelemetry(data);
        if (data.events?.length) setRecentEvents(current => {
          const combined = [...data.events, ...current];
          return combined.filter((item, index) => combined.findIndex(other => other.id === item.id) === index).slice(0, 8);
        });
      } catch (reason) {
        setStreamError(reason instanceof Error ? reason.message : 'Malformed monitoring message');
        setTelemetry(null);
        setMonitoring(false);
      }
    };
    socket.onerror = () => {
      if (socketRef.current === socket) {
        setStreamError(current => current || 'Live Monitoring WebSocket connection failed. Check that the backend and camera source are available.');
        setTelemetry(null);
      }
    };
    socket.onclose = event => {
      if (event.code !== 1000 && socketRef.current === socket) {
        setStreamError(current => current || `${event.reason || 'Monitoring disconnected.'} Retry the connection.`);
        setTelemetry(null);
        setMonitoring(false);
      }
    };
    return () => {
      if (socketRef.current === socket) socketRef.current = null;
      socket.close();
    };
  }, [selectedCamera?.id, retryKey, monitoring]);

  const retryStream = () => {
    const previousSocket = socketRef.current;
    socketRef.current = null;
    if (previousSocket && previousSocket.readyState < WebSocket.CLOSING) {
      previousSocket.close(1000, 'Camera reconnection requested');
    }
    setStreamError(null);
    setTelemetry(null);
    setStopping(false);
    setMonitoring(true);
    setRetryKey(value => value + 1);
  };
  const toggleMonitoring = () => {
    if (!monitoring) {
      setStreamError(null);
      setStopping(false);
      setMonitoring(true);
      return;
    }
    setStopping(true);
    if (socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify({ type: 'stop' }));
    else { setStopping(false); setMonitoring(false); setTelemetry(null); }
  };

  const count = (key: string) => telemetry?.summary?.[key] ?? '—';
  const sourceStatus = telemetry?.source_status
    || (monitoring ? 'CONNECTING' : streamError?.startsWith('CAMERA_SOURCE_UNAVAILABLE') ? 'OFFLINE' : streamError ? 'ERROR' : 'NOT MONITORED');

  return <div className="p-6 space-y-6">
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
      <div className="flex items-center gap-3"><div className="p-2.5 bg-indigo-950/60 text-indigo-400 rounded-xl border border-indigo-800/40"><CameraIcon className="w-5 h-5" /></div><div><h2 className="text-base font-bold text-white">Live Monitoring</h2><p className="text-xs text-slate-400">Processed frames and observations from the configured camera source.</p></div></div>
      <div className="flex items-center gap-3"><select value={selectedCamera?.id || ''} onChange={event => { setMonitoring(false); setStreamError(null); setSelectedCamera(cameras.find(camera => camera.id === event.target.value) || null); }} className="px-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-semibold text-white"><option value="">Select camera</option>{cameras.map(camera => <option key={camera.id} value={camera.id}>{camera.name} ({camera.location})</option>)}</select><button onClick={() => void loadCameras()} className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl" title="Refresh cameras"><RefreshCw className="w-4 h-4" /></button><button disabled={!selectedCamera || stopping} onClick={toggleMonitoring} className="px-3 py-2 rounded-xl bg-indigo-600 disabled:opacity-40 text-xs font-semibold text-white">{stopping ? 'Stopping...' : monitoring ? 'Stop monitoring' : 'Start monitoring'}</button></div>
    </div>
    {cameraLoading && <p className="text-sm text-slate-400">Loading cameras...</p>}
    {cameraError && <p role="alert" className="text-sm text-rose-300">Unable to load cameras: {cameraError} <button onClick={() => void loadCameras()} className="ml-2 underline">Retry</button></p>}
    {!cameraLoading && !cameraError && cameras.length === 0 && <p className="text-sm text-slate-400">No cameras configured.</p>}
    {streamError && <p role="alert" className="text-sm text-rose-300">Monitoring error: {streamError} <button onClick={retryStream} className="ml-2 underline">Retry</button></p>}

    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between"><span className="text-xs font-bold text-white">{selectedCamera?.name || 'Camera feed'}</span><span className="text-xs text-slate-400">{selectedCamera?.location || 'No camera selected'}</span></div>
        <div className="bg-black min-h-[400px] flex items-center justify-center">{telemetry?.frame ? <img src={telemetry.frame} alt="Processed live camera frame" className="w-full h-auto max-h-[550px] object-contain" /> : <div className="text-center text-sm text-slate-400 p-8">{cameraError || streamError || (monitoring ? 'Connecting to configured source...' : selectedCamera ? 'Start monitoring to open this source.' : 'No camera selected.')}</div>}</div>
        <div className="p-3 border-t border-slate-800 text-[11px] text-slate-400 flex justify-between"><span>Source: {selectedCamera?.source_type || '—'} · {sourceStatus}</span><span>{telemetry ? `${telemetry.fps} FPS` : 'Waiting for live frames'}</span></div>
      </div>
      <div className="space-y-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3"><h3 className="text-xs font-bold text-slate-400 uppercase">Live frame telemetry</h3><div className="grid grid-cols-2 gap-3"><div className="bg-slate-950 p-3 rounded-xl border border-slate-800"><span className="text-[10px] text-slate-400 uppercase block">People detected</span><span className="text-xl font-bold text-white">{count('total')}</span></div><div className="bg-slate-950 p-3 rounded-xl border border-slate-800"><span className="text-[10px] text-emerald-400 uppercase block">Verified</span><span className="text-xl font-bold text-emerald-400">{count('verified')}</span></div><div className="bg-slate-950 p-3 rounded-xl border border-slate-800 col-span-2"><span className="text-[10px] text-amber-400 uppercase block">Unverified</span><span className="text-xl font-bold text-amber-400">{count('unverified')}</span></div></div></div>
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3"><h3 className="text-xs font-bold text-slate-400 uppercase">Current detections</h3><div className="space-y-2 max-h-[350px] overflow-y-auto">{!telemetry ? <div className="text-sm text-slate-500">No live observation available.</div> : telemetry.detections.length === 0 ? <div className="text-sm text-slate-500">No people detected in the current frame.</div> : telemetry.detections.map((detection: any, index: number) => <div key={detection.track_id ?? `${index}-${detection.bbox?.join(',')}`} className="p-3 bg-slate-950 rounded-xl border border-slate-800 flex items-center justify-between"><div><div className="flex items-center gap-2"><span className="text-xs font-bold text-white">{detection.track_id == null ? 'Track ID unavailable' : `Track ${detection.track_id}`} · {detection.name || 'Unknown identity'}</span><span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">{detection.face_status || detection.status || 'Unverified'}</span></div><span className="text-[10px] text-slate-400 block mt-0.5">{detection.role || 'Role unknown'}{detection.college_id ? ` · ${detection.college_id}` : ''}{detection.department ? ` · ${detection.department}` : ''}{detection.similarity != null ? ` · ${(detection.similarity * 100).toFixed(1)}%` : ''}</span></div>{detection.status === 'VERIFIED' ? <ShieldCheck className="w-5 h-5 text-emerald-400" /> : <UserX className="w-5 h-5 text-amber-400" />}</div>)}</div></div>
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-3"><h3 className="text-xs font-bold text-slate-400 uppercase">Persisted camera events</h3>{recentEventsError ? <p role="alert" className="text-xs text-rose-300">Unable to load events: {recentEventsError}</p> : recentEvents.length ? recentEvents.map(event => <div key={event.id} className="text-xs text-slate-300 border-b border-slate-800 pb-2">{event.event_type.replaceAll('_', ' ')}{event.location ? ` · ${event.location}` : ''}</div>) : <div className="text-sm text-slate-500">No security events recorded.</div>}</div>
      </div>
    </div>
  </div>;
};
