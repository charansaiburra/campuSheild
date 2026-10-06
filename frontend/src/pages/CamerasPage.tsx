import React, { useEffect, useState } from 'react';
import { Camera as CameraIcon, Plus, Trash2, CheckCircle2, XCircle, Play } from 'lucide-react';
import { api } from '../services/api';
import { Camera } from '../types';

export const CamerasPage: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [sourceType, setSourceType] = useState('WEBCAM');
  const [sourceUrl, setSourceUrl] = useState('0');

  useEffect(() => {
    loadCameras();
  }, []);

  const loadCameras = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.getCameras();
      setCameras(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load cameras');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createCamera({ name, location, source_type: sourceType, source_url: sourceUrl });
      setShowModal(false);
      setName('');
      setLocation('');
      loadCameras();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this camera?')) return;
    try {
      await api.deleteCamera(id);
      loadCameras();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleTest = async (id: string) => {
    try {
      const res = await api.testCamera(id);
      alert(res.message);
      loadCameras();
    } catch (err: any) {
      alert(err.message);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-5 rounded-2xl">
        <div>
          <h2 className="text-xl font-bold text-white">Camera Streams & Device Management</h2>
          <p className="text-xs text-slate-400 mt-1">Configure Webcams, MP4 Files, and RTSP IP Camera Streams</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-xs rounded-xl shadow-lg transition"
        >
          <Plus className="w-4 h-4" />
          <span>Add New Camera</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {error && <p role="alert" className="md:col-span-2 lg:col-span-3 text-sm text-rose-300">Unable to load cameras: {error} <button onClick={() => void loadCameras()} className="ml-2 underline">Retry</button></p>}
        {loading && <p className="md:col-span-2 lg:col-span-3 text-sm text-slate-400">Loading cameras...</p>}
        {!loading && !error && cameras.length === 0 && <p className="md:col-span-2 lg:col-span-3 bg-slate-900 border border-slate-800 p-8 rounded-2xl text-center text-sm text-slate-400">No data available</p>}
        {!loading && !error && cameras.map((cam) => (
          <div key={cam.id} className="bg-slate-900 border border-slate-800 p-5 rounded-2xl flex flex-col justify-between space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-indigo-400 bg-indigo-950/60 px-2.5 py-1 rounded-full border border-indigo-800/40">
                  {cam.source_type}
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  cam.status === 'ONLINE' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40' : 'bg-rose-950 text-rose-400 border border-rose-800/40'
                }`}>
                  {cam.status}
                </span>
              </div>
              <h3 className="text-base font-bold text-white">{cam.name}</h3>
              <p className="text-xs text-slate-400 mt-0.5">Location: {cam.location}</p>
              <p className="text-[11px] text-slate-500 mt-2">Source address is hidden.</p>
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
              <button
                onClick={() => handleTest(cam.id)}
                className="text-xs text-slate-300 hover:text-white bg-slate-800 px-3 py-1.5 rounded-xl font-medium"
              >
                Test Connection
              </button>
              <button
                onClick={() => handleDelete(cam.id)}
                className="p-2 text-rose-400 hover:bg-rose-950/40 rounded-xl transition"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md space-y-4">
            <h3 className="text-lg font-bold text-white">Add Camera Device</h3>
            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1">Camera Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white"
                  placeholder="Main Entrance Camera"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Location</label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white"
                  placeholder="Gate 1"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Source Type</label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white"
                >
                  <option value="WEBCAM">Webcam (Index 0, 1)</option>
                  <option value="VIDEO_FILE">Recorded Video File (MP4)</option>
                  <option value="RTSP">RTSP / IP Camera Stream</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1">Source URL / Index</label>
                <input
                  type="text"
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white"
                  placeholder="0 or test_datas/testing_video.mp4 or rtsp://..."
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 text-white font-medium rounded-xl shadow"
                >
                  Save Camera
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
