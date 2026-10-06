import React, { useEffect, useState, useRef } from 'react';
import { UserPlus, ShieldCheck, Camera, Upload, Trash2, CheckCircle2, AlertCircle, RefreshCw, Search, Filter, Users, GraduationCap, Briefcase, ShieldAlert, UserCheck, AlertTriangle } from 'lucide-react';
import { api } from '../services/api';
import { CollegeMember } from '../types';

export const MembersPage: React.FC = () => {
  const [members, setMembers] = useState<CollegeMember[]>([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [activeEnrollMember, setActiveEnrollMember] = useState<CollegeMember | null>(null);

  // Filtering & Category Tabs
  const [activeTab, setActiveTab] = useState<'ALL' | 'STUDENT' | 'FACULTY' | 'STAFF' | 'VISITOR'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedDept, setSelectedDept] = useState('ALL');
  const [selectedFaceStatus, setSelectedFaceStatus] = useState('ALL');

  // Enrollment State
  const [enrollMethod, setEnrollMethod] = useState<'CAMERA' | 'UPLOAD'>('UPLOAD');
  const [sampleLabel, setSampleLabel] = useState<string>('Front');
  const [enrolledSamples, setEnrolledSamples] = useState<any[]>([]);

  // Member Registration Form
  const [name, setName] = useState('');
  const [collegeId, setCollegeId] = useState('');
  const [role, setRole] = useState('STUDENT');
  const [department, setDepartment] = useState('Computer Science');
  const [year, setYear] = useState('4th Year');
  const [email, setEmail] = useState('');

  // Camera State
  const videoRef = useRef<HTMLVideoElement>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [cameraGuidance, setCameraGuidance] = useState('Position your face inside the frame');
  
  // Processing Progress & Status
  const [isProcessing, setIsProcessing] = useState(false);
  const [processingStep, setProcessingStep] = useState<string | null>(null);
  const [enrollStatusMsg, setEnrollStatusMsg] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  // File Upload State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);

  useEffect(() => {
    loadMembers();
  }, [activeTab, searchQuery, selectedDept, selectedFaceStatus]);

  const loadMembers = async () => {
    setMembersLoading(true);
    setMembersError(null);
    try {
      const params: Record<string, any> = {};
      if (activeTab !== 'ALL') params.category = activeTab;
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (selectedDept !== 'ALL') params.department = selectedDept;
      if (selectedFaceStatus === 'ENROLLED') params.face_enrolled = true;
      if (selectedFaceStatus === 'NOT_ENROLLED') params.face_enrolled = false;

      const list = await api.getMembers(params);
      setMembers(list);
    } catch (e) {
      setMembersError(e instanceof Error ? e.message : 'Unable to load members');
    } finally {
      setMembersLoading(false);
    }
  };

  const loadMemberSamples = async (memberId: string) => {
    try {
      const list = await api.fetchApi(`/members/${memberId}/samples`);
      setEnrolledSamples(list);
    } catch (e) {
      setEnrolledSamples([]);
    }
  };

  const openEnrollModal = (member: CollegeMember) => {
    setActiveEnrollMember(member);
    setEnrollMethod('UPLOAD');
    setSampleLabel('Front');
    setEnrollStatusMsg(null);
    setProcessingStep(null);
    setSelectedFile(null);
    setUploadPreview(null);
    setCameraError(null);
    loadMemberSamples(member.id);
  };

  const closeEnrollModal = () => {
    stopWebcam();
    setActiveEnrollMember(null);
    setCameraActive(false);
    setSelectedFile(null);
    setUploadPreview(null);
    setEnrollStatusMsg(null);
    setProcessingStep(null);
    loadMembers();
  };

  const startWebcam = async () => {
    setCameraError(null);
    setEnrollStatusMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraActive(true);
        setCameraGuidance('Keep your face clearly visible and look directly into the camera');
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

  const runEnrollmentPipeline = async (imageInput: File | string, label: string) => {
    if (!activeEnrollMember) return;
    setIsProcessing(true);
    setEnrollStatusMsg(null);

    try {
      setProcessingStep('Sending image to backend face processing...');
      const res = await api.enrollFace(activeEnrollMember.id, imageInput, label);

      setProcessingStep('Enrollment successful!');
      setEnrollStatusMsg({
        type: 'success',
        message: res.message || `✓ Face sample '${label}' enrolled successfully! (Quality: ${res.quality_score})`
      });

      setSelectedFile(null);
      setUploadPreview(null);
      loadMemberSamples(activeEnrollMember.id);
      loadMembers();
    } catch (err: any) {
      setProcessingStep(null);
      setEnrollStatusMsg({
        type: 'error',
        message: err.message || 'Face enrollment failed. Please try again with a clearer image.'
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const captureCameraSample = async (label: string) => {
    if (!videoRef.current || !activeEnrollMember) return;
    const canvas = document.createElement('canvas');
    if (!videoRef.current.videoWidth || !videoRef.current.videoHeight) {
      setEnrollStatusMsg({ type: 'error', message: 'Camera has not produced a frame yet. Wait for the video preview and try again.' });
      return;
    }
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0);
    const base64 = canvas.toDataURL('image/jpeg', 0.92);

    await runEnrollmentPipeline(base64, label);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    setEnrollStatusMsg(null);
    setProcessingStep(null);

    if (file) {
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png'];
      if (!validTypes.includes(file.type)) {
        setEnrollStatusMsg({
          type: 'error',
          message: 'Invalid file format. Please select a valid .jpg, .jpeg, or .png photo.'
        });
        return;
      }
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setUploadPreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const processUploadedPhoto = async () => {
    if (!selectedFile || !activeEnrollMember) return;
    await runEnrollmentPipeline(selectedFile, sampleLabel);
  };

  const handleDeleteSample = async (sampleId: string) => {
    if (!activeEnrollMember) return;
    try {
      await api.fetchApi(`/members/${activeEnrollMember.id}/samples/${sampleId}`, { method: 'DELETE' });
      loadMemberSamples(activeEnrollMember.id);
      loadMembers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleCreateMember = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await api.createMember({
        name,
        college_id: collegeId,
        role,
        department,
        year,
        email
      });
      setShowAddModal(false);
      setName('');
      setCollegeId('');

      // Transactional flow: Immediately open face enrollment modal for newly registered member
      openEnrollModal(created);
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDeleteMember = async (id: string) => {
    if (!confirm('Deactivate this member and remove stored face templates? Historical event records will be retained.')) return;
    try {
      await api.deleteMember(id);
      loadMembers();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Metrics Calculation
  const totalCount = members.length;
  const studentCount = members.filter(m => m.role === 'STUDENT').length;
  const facultyCount = members.filter(m => m.role === 'FACULTY').length;
  const staffCount = members.filter(m => ['STAFF', 'TEACHING_STAFF', 'NON_TEACHING_STAFF', 'SECURITY_STAFF'].includes(m.role)).length;
  const visitorCount = members.filter(m => ['VISITOR', 'AUTHORIZED_VISITOR'].includes(m.role)).length;
  const enrolledCount = members.filter(m => m.face_enrolled).length;
  const notEnrolledCount = totalCount - enrolledCount;
  const memberMetric = (value: number) => membersLoading || membersError ? '—' : value;

  const getRoleCategoryBadge = (roleStr: string) => {
    switch (roleStr) {
      case 'STUDENT':
        return <span className="bg-blue-950 text-blue-400 border border-blue-800/50 px-2.5 py-1 rounded-full text-[10px] font-bold">Student</span>;
      case 'FACULTY':
        return <span className="bg-purple-950 text-purple-400 border border-purple-800/50 px-2.5 py-1 rounded-full text-[10px] font-bold">Faculty</span>;
      case 'TEACHING_STAFF':
      case 'NON_TEACHING_STAFF':
      case 'SECURITY_STAFF':
      case 'STAFF':
        return <span className="bg-amber-950 text-amber-400 border border-amber-800/50 px-2.5 py-1 rounded-full text-[10px] font-bold">Staff</span>;
      case 'AUTHORIZED_VISITOR':
      case 'VISITOR':
        return <span className="bg-emerald-950 text-emerald-400 border border-emerald-800/50 px-2.5 py-1 rounded-full text-[10px] font-bold">Visitor</span>;
      default:
        return <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-full text-[10px] font-bold">{roleStr}</span>;
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Top Header & New Member Trigger */}
      <div className="flex items-center justify-between bg-slate-900 border border-slate-800 p-5 rounded-2xl shadow-xl">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-indigo-400" />
            College Member Registry
          </h2>
          <p className="text-xs text-slate-400 mt-1">Manage Students, Faculty, Staff, and Visitors with AI-Powered Face Enrollment</p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-indigo-600/30 transition"
        >
          <UserPlus className="w-4 h-4" />
          <span>Register New Member</span>
        </button>
      </div>

      {/* Role Summary Statistics Dashboard */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-slate-400 text-[10px] font-bold uppercase tracking-wider block">Total</span>
          <span className="text-xl font-black text-white">{memberMetric(totalCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-blue-400 text-[10px] font-bold uppercase tracking-wider block">Students</span>
          <span className="text-xl font-black text-blue-300">{memberMetric(studentCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-purple-400 text-[10px] font-bold uppercase tracking-wider block">Faculty</span>
          <span className="text-xl font-black text-purple-300">{memberMetric(facultyCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-amber-400 text-[10px] font-bold uppercase tracking-wider block">Staff</span>
          <span className="text-xl font-black text-amber-300">{memberMetric(staffCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-emerald-400 text-[10px] font-bold uppercase tracking-wider block">Visitors</span>
          <span className="text-xl font-black text-emerald-300">{memberMetric(visitorCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-emerald-400 text-[10px] font-bold uppercase tracking-wider block">Face Enrolled</span>
          <span className="text-xl font-black text-emerald-400">{memberMetric(enrolledCount)}</span>
        </div>
        <div className="bg-slate-900 border border-slate-800 p-4 rounded-2xl text-center">
          <span className="text-rose-400 text-[10px] font-bold uppercase tracking-wider block">Not Enrolled</span>
          <span className="text-xl font-black text-rose-400">{memberMetric(notEnrolledCount)}</span>
        </div>
      </div>

      {/* Identity Category Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
        <button
          onClick={() => setActiveTab('ALL')}
          className={`px-4 py-2 text-xs font-bold rounded-xl transition ${
            activeTab === 'ALL'
              ? 'bg-indigo-600 text-white shadow'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          All Members ({totalCount})
        </button>
        <button
          onClick={() => setActiveTab('STUDENT')}
          className={`px-4 py-2 text-xs font-bold rounded-xl transition flex items-center gap-1.5 ${
            activeTab === 'STUDENT'
              ? 'bg-blue-600 text-white shadow'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <GraduationCap className="w-3.5 h-3.5" />
          Students ({studentCount})
        </button>
        <button
          onClick={() => setActiveTab('FACULTY')}
          className={`px-4 py-2 text-xs font-bold rounded-xl transition flex items-center gap-1.5 ${
            activeTab === 'FACULTY'
              ? 'bg-purple-600 text-white shadow'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <Briefcase className="w-3.5 h-3.5" />
          Faculty ({facultyCount})
        </button>
        <button
          onClick={() => setActiveTab('STAFF')}
          className={`px-4 py-2 text-xs font-bold rounded-xl transition flex items-center gap-1.5 ${
            activeTab === 'STAFF'
              ? 'bg-amber-600 text-white shadow'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          Staff ({staffCount})
        </button>
        <button
          onClick={() => setActiveTab('VISITOR')}
          className={`px-4 py-2 text-xs font-bold rounded-xl transition flex items-center gap-1.5 ${
            activeTab === 'VISITOR'
              ? 'bg-emerald-600 text-white shadow'
              : 'bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200'
          }`}
        >
          <UserCheck className="w-3.5 h-3.5" />
          Visitors ({visitorCount})
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
        <div className="relative md:col-span-2">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Search by Name or College ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        </div>

        <div>
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="w-full p-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
          >
            <option value="ALL">All Departments</option>
            <option value="Computer Science">Computer Science</option>
            <option value="Electrical Engineering">Electrical Engineering</option>
            <option value="Mechanical Engineering">Mechanical Engineering</option>
            <option value="Civil Engineering">Civil Engineering</option>
            <option value="Administrative">Administrative</option>
          </select>
        </div>

        <div>
          <select
            value={selectedFaceStatus}
            onChange={(e) => setSelectedFaceStatus(e.target.value)}
            className="w-full p-2 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
          >
            <option value="ALL">All Face Statuses</option>
            <option value="ENROLLED">Enrolled Only</option>
            <option value="NOT_ENROLLED">Not Enrolled Only</option>
          </select>
        </div>
      </div>

      {/* Member List Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
        {membersError && <p role="alert" className="p-4 text-sm text-rose-300">Unable to load members: {membersError} <button onClick={() => void loadMembers()} className="ml-2 underline">Retry</button></p>}
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
              <th className="py-3.5 px-4">Name</th>
              <th className="py-3.5 px-4">College ID</th>
              <th className="py-3.5 px-4">Role</th>
              <th className="py-3.5 px-4">Department</th>
              <th className="py-3.5 px-4">Face Status</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {membersLoading ? (
              <tr><td colSpan={6} className="py-8 text-center text-slate-400">Loading members...</td></tr>
            ) : membersError ? null : members.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-500 font-medium">
                  No members found matching the selected filters.
                </td>
              </tr>
            ) : (
              members.map((m) => (
                <tr key={m.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-3.5 px-4 font-bold text-white">{m.name}</td>
                  <td className="py-3.5 px-4 font-mono text-indigo-300">{m.college_id}</td>
                  <td className="py-3.5 px-4">{getRoleCategoryBadge(m.role)}</td>
                  <td className="py-3.5 px-4">{m.department || 'N/A'}</td>
                  <td className="py-3.5 px-4">
                    {m.face_enrolled ? (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-400 text-[10px] font-bold border border-emerald-800/40">
                        <ShieldCheck className="w-3.5 h-3.5" /> Enrolled ({m.sample_count || 1} Samples)
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-950 text-amber-400 text-[10px] font-bold border border-amber-800/40">
                        <AlertTriangle className="w-3.5 h-3.5" /> Not Enrolled
                      </span>
                    )}
                  </td>
                  <td className="py-3.5 px-4 text-right space-x-2">
                    <button
                      onClick={() => openEnrollModal(m)}
                      className="px-3.5 py-1.5 bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-xl text-[11px] font-semibold transition"
                    >
                      Face Enrollment
                    </button>
                    <button
                      onClick={() => handleDeleteMember(m.id)}
                      className="p-1.5 text-rose-400 hover:bg-rose-950/40 rounded-xl transition"
                      title="Delete Member"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Add Member Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 w-full max-w-md space-y-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white">Register New College Member</h3>
            <form onSubmit={handleCreateMember} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 mb-1 font-semibold">Full Name</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. Charan Sai"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">College / Employee ID</label>
                <input
                  type="text"
                  value={collegeId}
                  onChange={(e) => setCollegeId(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. CS-2026-001"
                  required
                />
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">Role / Identity Category</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-indigo-500 focus:outline-none"
                >
                  <option value="STUDENT">Student</option>
                  <option value="FACULTY">Faculty</option>
                  <option value="STAFF">Staff</option>
                  <option value="AUTHORIZED_VISITOR">Visitor</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 mb-1 font-semibold">Department</label>
                <input
                  type="text"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-white focus:border-indigo-500 focus:outline-none"
                  placeholder="e.g. Computer Science"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-slate-800 text-slate-300 rounded-xl font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl shadow"
                >
                  Save & Continue to Face Enrollment
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main Face Enrollment Modal (Two Options: Use Camera OR Upload Photo) */}
      {activeEnrollMember && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 w-full max-w-2xl space-y-6 shadow-2xl my-8">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-lg font-bold text-white">Face Enrollment</h3>
                <p className="text-xs text-slate-400">
                  Registering Member: <span className="text-indigo-400 font-semibold">{activeEnrollMember.name}</span> ({activeEnrollMember.college_id})
                </p>
              </div>
              <button
                onClick={closeEnrollModal}
                className="text-xs font-bold text-slate-400 hover:text-white px-3 py-1.5 bg-slate-800 rounded-xl"
              >
                Close
              </button>
            </div>

            {/* Method Choice Cards */}
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => {
                  setEnrollMethod('UPLOAD');
                  stopWebcam();
                  setEnrollStatusMsg(null);
                  setProcessingStep(null);
                }}
                className={`p-4 rounded-2xl border text-left transition flex items-center gap-3 ${
                  enrollMethod === 'UPLOAD'
                    ? 'bg-emerald-950/60 border-emerald-500 text-white shadow-lg'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="p-3 bg-emerald-600/20 text-emerald-400 rounded-xl">
                  <Upload className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Upload Photo</h4>
                  <p className="text-[10px] text-slate-400">Select JPG/PNG photo files via multipart upload</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setEnrollMethod('CAMERA');
                  startWebcam();
                }}
                className={`p-4 rounded-2xl border text-left transition flex items-center gap-3 ${
                  enrollMethod === 'CAMERA'
                    ? 'bg-indigo-950/60 border-indigo-500 text-white shadow-lg'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <div className="p-3 bg-indigo-600/20 text-indigo-400 rounded-xl">
                  <Camera className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white">Use Camera</h4>
                  <p className="text-[10px] text-slate-400">Capture live webcam video samples</p>
                </div>
              </button>
            </div>

            {/* Step-by-Step Processing Status Overlay */}
            {processingStep && (
              <div className="bg-indigo-950/40 border border-indigo-800/60 p-3.5 rounded-2xl text-center space-y-2">
                <div className="flex items-center justify-center gap-2 text-indigo-300 font-bold text-xs">
                  <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                  <span>Processing Step: {processingStep}</span>
                </div>
                <div className="w-full bg-slate-950 h-1.5 rounded-full overflow-hidden">
                  <div className="bg-indigo-500 h-full w-3/4 animate-pulse rounded-full" />
                </div>
              </div>
            )}

            {/* Validation Message Box */}
            {enrollStatusMsg && (
              <div className={`p-4 rounded-2xl text-xs font-semibold border flex items-start gap-2.5 ${
                enrollStatusMsg.type === 'error'
                  ? 'bg-rose-950/60 text-rose-300 border-rose-800/60'
                  : 'bg-emerald-950/60 text-emerald-300 border-emerald-800/60'
              }`}>
                {enrollStatusMsg.type === 'error' ? (
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                )}
                <span>{enrollStatusMsg.message}</span>
              </div>
            )}

            {/* Option 1: Upload Photo View */}
            {enrollMethod === 'UPLOAD' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Sample Angle Label</label>
                    <select
                      value={sampleLabel}
                      onChange={(e) => setSampleLabel(e.target.value)}
                      className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-xl text-xs text-white focus:outline-none"
                    >
                      <option value="Front">Front Pose</option>
                      <option value="Slight Left">Slight Left Pose</option>
                      <option value="Slight Right">Slight Right Pose</option>
                    </select>
                  </div>

                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Select Face Image (.jpg, .png)</label>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/jpg"
                      onChange={handleFileChange}
                      className="w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-emerald-600/20 file:text-emerald-300 hover:file:bg-emerald-600 hover:file:text-white transition"
                    />
                  </div>
                </div>

                {uploadPreview && (
                  <div className="relative bg-slate-950 p-3 rounded-2xl border border-slate-800 flex items-center justify-center max-h-[220px]">
                    <img src={uploadPreview} alt="Selected Preview" className="max-h-[200px] object-contain rounded-xl" />
                  </div>
                )}

                <button
                  disabled={!selectedFile || isProcessing}
                  onClick={processUploadedPhoto}
                  className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-600/20 flex items-center justify-center gap-2 transition"
                >
                  <Upload className="w-4 h-4" />
                  <span>Process & Enroll Selected Photo</span>
                </button>
              </div>
            )}

            {/* Option 2: Use Camera View */}
            {enrollMethod === 'CAMERA' && (
              <div className="space-y-4">
                {cameraError ? (
                  <div className="p-4 bg-rose-950/60 border border-rose-800 text-rose-300 rounded-2xl text-xs font-semibold flex items-center gap-2">
                    <AlertCircle className="w-5 h-5 text-rose-400" />
                    <span>{cameraError}</span>
                  </div>
                ) : (
                  <div className="relative bg-black rounded-2xl overflow-hidden min-h-[300px] flex items-center justify-center border border-slate-800">
                    <video ref={videoRef} className="w-full h-full object-cover max-h-[360px]" />
                    <div className="absolute inset-0 border-2 border-dashed border-indigo-400/60 rounded-3xl m-10 pointer-events-none flex items-center justify-center">
                      <span className="text-[11px] font-semibold text-indigo-300 bg-slate-950/80 px-3 py-1 rounded-full border border-indigo-800/40">
                        {cameraGuidance}
                      </span>
                    </div>
                  </div>
                )}

                <div className="space-y-2">
                  <span className="text-xs font-bold text-slate-300 block">Capture Live Camera Samples:</span>
                  <div className="grid grid-cols-3 gap-3">
                    <button
                      disabled={isProcessing || !cameraActive}
                      onClick={() => captureCameraSample('Front')}
                      className="py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow flex items-center justify-center gap-1.5"
                    >
                      <Camera className="w-4 h-4" />
                      <span>Front Pose</span>
                    </button>
                    <button
                      disabled={isProcessing || !cameraActive}
                      onClick={() => captureCameraSample('Slight Left')}
                      className="py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow flex items-center justify-center gap-1.5"
                    >
                      <Camera className="w-4 h-4" />
                      <span>Slight Left</span>
                    </button>
                    <button
                      disabled={isProcessing || !cameraActive}
                      onClick={() => captureCameraSample('Slight Right')}
                      className="py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow flex items-center justify-center gap-1.5"
                    >
                      <Camera className="w-4 h-4" />
                      <span>Slight Right</span>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* Enrolled Samples List */}
            <div className="border-t border-slate-800 pt-4 space-y-2 text-left">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300">Enrolled Face Representations ({enrolledSamples.length})</span>
                {enrolledSamples.length > 0 && (
                  <span className="text-[10px] font-bold text-emerald-400 bg-emerald-950 px-2.5 py-0.5 rounded-full border border-emerald-800">
                    Quality Check: Passed ✓
                  </span>
                )}
              </div>

              {enrolledSamples.length === 0 ? (
                <p className="text-[11px] text-slate-500 italic">No face samples enrolled yet. Use Camera or Upload Photo to enroll samples.</p>
              ) : (
                <div className="grid grid-cols-3 gap-2">
                  {enrolledSamples.map((s) => (
                    <div key={s.id} className="p-2.5 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between text-xs">
                      <div>
                        <span className="font-bold text-white block">{s.sample_label}</span>
                        <span className="text-[10px] text-slate-400 font-mono">Quality: {s.quality_score}</span>
                      </div>
                      <button
                        onClick={() => handleDeleteSample(s.id)}
                        className="text-rose-400 hover:text-rose-300 p-1"
                        title="Remove Sample"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
