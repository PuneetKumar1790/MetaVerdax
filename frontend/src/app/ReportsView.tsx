import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, Download, AlertTriangle, Loader2 } from 'lucide-react';
import { api, type ReportItem } from '../lib/api';

export default function ReportsView() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const data = await api.getReports();
        setReports(data);
      } catch {
        setError('Unable to fetch reports. Is your backend running?');
      } finally {
        setLoading(false);
      }
    };
    fetchReports();
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-2xl font-bold text-white">Reports</h1>
        <p className="text-sm text-white/30 mt-1">
          Download generated PDF audit and compliance reports.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 text-brand-cyan animate-spin" />
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 rounded-xl bg-brand-amber/10 border border-brand-amber/20 text-sm text-brand-amber">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {!loading && !error && reports.length === 0 && (
        <div className="text-center py-20 text-white/20">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No reports generated yet. Run a validation to generate one.</p>
        </div>
      )}

      {!loading && !error && reports.length > 0 && (
        <div className="grid gap-4">
          {reports.map((report, i) => (
            <motion.div
              key={report.id}
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: i * 0.05 }}
              className="flex items-center justify-between p-4 rounded-xl border border-white/5 bg-white/[0.02] hover:border-brand-cyan/15 transition-all duration-300"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-brand-cyan/5 border border-brand-cyan/15 flex items-center justify-center">
                  <FileText className="w-5 h-5 text-brand-cyan" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white/80">{report.filename}</p>
                  <p className="text-xs text-white/30 mt-0.5">
                    {report.dataset} · {report.created_at}
                  </p>
                </div>
              </div>
              <a
                href={api.downloadReportUrl(report.download_url)}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-brand-cyan/20 text-xs font-medium text-brand-cyan hover:bg-brand-cyan/10 transition-all"
              >
                <Download className="w-3.5 h-3.5" />
                Download
              </a>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
