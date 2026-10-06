import React, { useState, useRef, useEffect } from 'react';
import { Camera, Upload, ShieldCheck, AlertCircle, RefreshCw, CheckCircle2, UserCheck, AlertTriangle, Eye, UserX, Clock, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { formatCampusTimestamp } from '../utils/date';

interface PersonIdentificationPageProps {
  onNavigate?: (tab: string) => void;
}

export const PersonIdentificationPage: React.FC<PersonIdentificationPageProps> = ({ onNavigate }) => {
  const [method, setMethod] = useState<'UPLOAD' | 'CAMERA'>('UPLOAD');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);

  // Camera state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [capturedBase64, setCapturedBase64] = useState<string | null>(null);

  // Processing state & step feedback
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState<string | null>(null);
  const [result, setResult] = useState<any | null>(null);

  // Audit history log
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const logs = await api.getIdentificationHistory();
      setHistory(logs);
    } catch (e) {
      setHistoryError(e instanceof Error ? e.message : 'Unable to load identification history');
    } finally {
      setHistoryLoading(false);
    }
  };

  const startWebcam = async () => {
    setCameraError(null);
    setCapturedBase64(null);
    setResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraActive(true);
      }
    } catch (e: any) {
      setCameraActive(false);
      setCameraError('Camera permission denied or camera device unavailable. Please use [Upload Photo] option.');
    }
  };

  const stopWebcam = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject as MediaStream;
      stream.getTracks().forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    setCameraActive(false);
  };

  const handleCaptureFrame = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    if (!videoRef.current.videoWidth || !videoRef.current.videoHeight) {
      setCameraError('Camera has not produced a frame yet. Wait for the preview and try again.');
      return;
    }
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0);
    const base64 = canvas.toDataURL('image/jpeg', 0.92);
    setCapturedBase64(base64);
    setImagePreview(base64);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setResult(null);
    if (file) {
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
      if (!validTypes.includes(file.type)) {
        alert('Please select a valid .jpg, .jpeg, or .png photo file.');
        return;
      }
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleIdentifyPerson = async () => {
    const payload = method === 'UPLOAD' ? selectedFile : (capturedBase64 || imagePreview);
    if (!payload) return;

    setIsProcessing(true);
    setProcessingStep('Uploading...');
    setResult(null);

    try {
      setProcessingStep('Backend is processing the submitted image...');

      const response = await api.identifyPerson(payload);
      setResult(response);
      void loadHistory();
    } catch (err: any) {
      setResult({
        success: false,
        status: 'ERROR',
        message: err.message || 'Unable to process the image.'
      });
    } finally {
      setIsProcessing(false);
      setProcessingStep(null);
    }
  };

  const resetSelection = () => {
    setResult(null);
    setSelectedFile(null);
    setImagePreview(null);
    setCapturedBase64(null);
    if (method === 'CAMERA') {
      startWebcam();
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Header Banner */}
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <UserCheck className="w-6 h-6 text-indigo-400" />
            Person Identification
          </h2>
          <p className="text-xs text-slate-400 mt-1">Upload or capture a face to search enrolled college members</p>
        </div>
      </div>

      {/* Main Grid: Input & Options vs Results */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Side: Submission & Capture Controls */}
        <div className="lg:col-span-7 space-y-5">
          {/* Method Choice Buttons */}
          <div className="grid grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => {
                setMethod('UPLOAD');
                stopWebcam();
                resetSelection();
              }}
              className={`p-4 rounded-2xl border text-left transition flex items-center gap-3 ${
                method === 'UPLOAD'
                  ? 'bg-emerald-950/60 border-emerald-500 text-white shadow-lg'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="p-3 bg-emerald-600/20 text-emerald-400 rounded-xl">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Upload Photo</h4>
                <p className="text-[10px] text-slate-400">Select JPG/PNG photo file</p>
              </div>
            </button>

            <button
              type="button"
              onClick={() => {
                setMethod('CAMERA');
                resetSelection();
                startWebcam();
              }}
              className={`p-4 rounded-2xl border text-left transition flex items-center gap-3 ${
                method === 'CAMERA'
                  ? 'bg-indigo-950/60 border-indigo-500 text-white shadow-lg'
                  : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <div className="p-3 bg-indigo-600/20 text-indigo-400 rounded-xl">
                <Camera className="w-6 h-6" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-white">Use Camera</h4>
                <p className="text-[10px] text-slate-400">Capture live camera frame</p>
              </div>
            </button>
          </div>

          {/* Option 1: File Upload Box */}
          {method === 'UPLOAD' && (
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
              <label className="block text-xs font-bold text-slate-300">Select Photograph</label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/jpg"
                onChange={handleFileChange}
                className="w-full text-xs text-slate-400 file:mr-4 file:py-2.5 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-emerald-600/20 file:text-emerald-300 hover:file:bg-emerald-600 hover:file:text-white transition"
              />

              {imagePreview && (
                <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800 flex flex-col items-center justify-center space-y-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Image Preview</span>
                  <img src={imagePreview} alt="Preview" className="max-h-[260px] object-contain rounded-xl border border-slate-800" />
                </div>
              )}

              <button
                disabled={!selectedFile || isProcessing}
                onClick={handleIdentifyPerson}
                className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold rounded-xl text-xs shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition"
              >
                <Eye className="w-4 h-4" />
                <span>Identify Person</span>
              </button>
            </div>
          )}

          {/* Option 2: Live Camera View */}
          {method === 'CAMERA' && (
            <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl space-y-4">
              {cameraError ? (
                <div className="p-4 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-2xl text-xs font-semibold flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
                  <span>{cameraError}</span>
                </div>
              ) : (
                <div className="relative bg-black rounded-2xl overflow-hidden min-h-[320px] flex items-center justify-center border border-slate-800">
                  <video ref={videoRef} className="w-full h-full object-cover max-h-[360px]" />
                  <div className="absolute inset-0 border-2 border-dashed border-indigo-400/60 rounded-3xl m-10 pointer-events-none flex items-center justify-center">
                    <span className="text-[11px] font-semibold text-indigo-300 bg-slate-950/80 px-3 py-1 rounded-full border border-indigo-800/40">
                      Position face inside alignment guide
                    </span>
                  </div>
                </div>
              )}

              {capturedBase64 && (
                <div className="bg-slate-950 p-3 rounded-2xl border border-slate-800 flex items-center justify-center gap-3">
                  <img src={capturedBase64} alt="Captured" className="h-16 w-16 object-cover rounded-xl border border-indigo-500" />
                  <div className="text-xs">
                    <span className="font-bold text-emerald-400 block">✓ Frame Captured</span>
                    <span className="text-[10px] text-slate-400">Ready for FaceNet identification</span>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <button
                  disabled={!cameraActive || isProcessing}
                  onClick={handleCaptureFrame}
                  className="py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-white font-bold rounded-xl text-xs flex items-center justify-center gap-2"
                >
                  <Camera className="w-4 h-4 text-indigo-400" />
                  <span>Capture Frame</span>
                </button>

                <button
                  disabled={!capturedBase64 || isProcessing}
                  onClick={handleIdentifyPerson}
                  className="py-3 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-bold rounded-xl text-xs shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2"
                >
                  <Eye className="w-4 h-4" />
                  <span>Identify Person</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Right Side: Step-by-Step Processing & Result Card */}
        <div className="lg:col-span-5 space-y-5">
          {/* Step-by-Step Processing Overlay */}
          {processingStep && (
            <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl text-center space-y-3 shadow-xl">
              <div className="flex items-center justify-center gap-2 text-indigo-300 font-bold text-xs">
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                <span>Identification Step: {processingStep}</span>
              </div>
              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden">
                <div className="bg-indigo-500 h-full w-4/5 animate-pulse rounded-full" />
              </div>
            </div>
          )}

          {/* Idle State */}
          {!result && !processingStep && (
            <div className="bg-slate-900 border border-slate-800 p-8 rounded-2xl text-center space-y-3">
              <div className="p-4 bg-slate-950 w-16 h-16 mx-auto rounded-full border border-slate-800 flex items-center justify-center text-slate-500">
                <Eye className="w-8 h-8" />
              </div>
              <h3 className="text-sm font-bold text-white">No Face Submitted Yet</h3>
              <p className="text-xs text-slate-400 max-w-xs mx-auto">
                Upload a photo or capture a live camera frame to begin face identification against registered college members.
              </p>
            </div>
          )}

          {/* Result 1: VERIFIED PERSON */}
          {result && result.status === 'VERIFIED' && result.member && (
            <div className="bg-slate-900 border border-emerald-500/50 p-6 rounded-2xl space-y-5 shadow-2xl">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-sm font-bold text-emerald-400 uppercase tracking-wider">PERSON IDENTIFIED</h3>
                </div>
                <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950 px-2.5 py-1 rounded-full border border-emerald-800">
                  Status: Verified
                </span>
              </div>

              {/* Person Details Card */}
              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Full Name</span>
                  <span className="font-bold text-white text-sm">{result.member.name}</span>
                </div>

                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">College / Member ID</span>
                  <span className="font-mono font-bold text-indigo-300">{result.member.college_id}</span>
                </div>

                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Role</span>
                  <span className="font-bold text-blue-400 bg-blue-950 px-2.5 py-0.5 rounded-full border border-blue-800/40">
                    {result.member.role}
                  </span>
                </div>

                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Department</span>
                  <span className="font-semibold text-slate-200">{result.member.department || 'N/A'}</span>
                </div>

                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Face Similarity Score</span>
                  <span className="font-mono font-black text-emerald-400 text-sm">
                    {(result.similarity * 100).toFixed(2)}%
                  </span>
                </div>

                <div className="flex items-center justify-between bg-slate-950 p-3 rounded-xl border border-slate-800">
                  <span className="text-slate-400">Enrollment Status</span>
                  <span className="font-semibold text-emerald-400">Enrolled ({result.member.sample_count || 1} Samples)</span>
                </div>
              </div>

              {/* Actions */}
              <div className="pt-2 flex items-center justify-between gap-3">
                <button
                  onClick={resetSelection}
                  className="w-1/2 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-xl transition"
                >
                  Try Another Image
                </button>
                {onNavigate && (
                  <button
                    onClick={() => onNavigate('members')}
                    className="w-1/2 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow flex items-center justify-center gap-1.5 transition"
                  >
                    <span>View Member</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Result 2: UNKNOWN / UNVERIFIED PERSON */}
          {result && result.status === 'UNKNOWN' && (
            <div className="bg-slate-900 border border-amber-500/50 p-6 rounded-2xl space-y-4 shadow-2xl">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <UserX className="w-5 h-5 text-amber-400" />
                <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider">NO REGISTERED MATCH</h3>
              </div>

              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <span className="text-[11px] font-bold text-amber-300 block">Status: Unknown / Unverified</span>
                <p className="text-xs text-slate-300 leading-relaxed">
                  No sufficiently reliable match was found in the enrolled college-member database.
                </p>

                {result.similarity > 0 && (
                  <div className="pt-2 flex items-center justify-between text-[11px] border-t border-slate-800/60">
                    <span className="text-slate-400">Highest Candidate Similarity:</span>
                    <span className="font-mono text-slate-300">{(result.similarity * 100).toFixed(2)}% (Below Threshold)</span>
                  </div>
                )}
              </div>

              <button
                onClick={resetSelection}
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-xl transition"
              >
                Try Another Image
              </button>
            </div>
          )}

          {/* Result 3: ERROR / MULTIPLE FACES / NO FACE / POOR QUALITY */}
          {result && ['NO_FACE', 'MULTIPLE_FACES', 'POOR_QUALITY', 'ERROR'].includes(result.status) && (
            <div className="bg-slate-900 border border-rose-500/50 p-6 rounded-2xl space-y-4 shadow-2xl">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                <h3 className="text-sm font-bold text-rose-400 uppercase tracking-wider">
                  {result.status === 'MULTIPLE_FACES' ? 'MULTIPLE FACES DETECTED' : result.status === 'NO_FACE' ? 'NO FACE DETECTED' : 'QUALITY ISSUE'}
                </h3>
              </div>

              <p className="text-xs text-rose-200 bg-rose-950/40 p-3.5 rounded-xl border border-rose-900/40 font-medium">
                {result.message}
              </p>

              <button
                onClick={resetSelection}
                className="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-xl transition"
              >
                Try Another Image
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Identification History Table (Audit Log) */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3 shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-indigo-400" />
            Identification History (Audit Log)
          </h3>
          <span className="text-[10px] text-slate-400">Authorized Officer Log</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                <th className="py-3 px-4">Date / Time</th>
                <th className="py-3 px-4">Result</th>
                <th className="py-3 px-4">Matched Member</th>
                <th className="py-3 px-4">College ID</th>
                <th className="py-3 px-4">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {historyError ? (
                <tr><td colSpan={5} className="py-6 text-center text-rose-300">Unable to load identification history: {historyError} <button onClick={() => void loadHistory()} className="ml-2 underline">Retry</button></td></tr>
              ) : historyLoading ? (
                <tr><td colSpan={5} className="py-6 text-center text-slate-400">Loading identification history...</td></tr>
              ) : history.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500">
                    No identification history recorded yet.
                  </td>
                </tr>
              ) : (
                history.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400">
                      {formatCampusTimestamp(log.timestamp)}
                    </td>
                    <td className="py-3 px-4">
                      {log.status === 'VERIFIED' ? (
                        <span className="bg-emerald-950 text-emerald-400 border border-emerald-800/40 px-2 py-0.5 rounded-full text-[10px] font-bold">
                          Verified
                        </span>
                      ) : (
                        <span className="bg-amber-950 text-amber-400 border border-amber-800/40 px-2 py-0.5 rounded-full text-[10px] font-bold">
                          Unknown
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">{log.member_name}</td>
                    <td className="py-3 px-4 font-mono text-indigo-300">{log.college_id}</td>
                    <td className="py-3 px-4 text-slate-400 text-[11px]">{log.description}</td>
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
