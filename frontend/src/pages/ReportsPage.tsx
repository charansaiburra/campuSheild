import React, { useState } from 'react';
import { Download, FileText, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

export const ReportsPage: React.FC = () => {
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const exportEvents = async () => {
    setExporting(true);
    setError(null);
    try {
      const blob = await api.downloadCsvReport();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'campus_security_events.csv';
      link.click();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Could not export event records');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="bg-slate-900 border border-slate-800 p-5 rounded-2xl">
        <h2 className="text-xl font-bold text-white">Security Reports</h2>
        <p className="text-xs text-slate-400 mt-1">Export persisted security event records.</p>
      </div>
      <section className="bg-slate-900 border border-slate-800 p-6 rounded-2xl max-w-2xl">
        <div className="flex items-start gap-3">
          <FileText className="w-5 h-5 text-indigo-400 mt-0.5" />
          <div className="flex-1">
            <h3 className="text-sm font-bold text-white">Security events CSV</h3>
            <p className="text-xs text-slate-400 mt-1">The export contains records currently stored in the security event database.</p>
            {error && <p role="alert" className="mt-3 text-xs text-rose-300 flex items-center gap-2"><AlertCircle className="w-4 h-4" />{error}</p>}
            <button onClick={() => void exportEvents()} disabled={exporting} className="mt-4 inline-flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl">
              <Download className="w-4 h-4" />{exporting ? 'Exporting…' : 'Export event CSV'}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
};
