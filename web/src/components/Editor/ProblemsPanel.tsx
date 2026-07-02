'use client';

import { useState, useEffect, useCallback } from 'react';
import { lspDiagnostics, type LSPDiagnostic } from '@/lib/api';
import { useAppStore } from '@/lib/store';

const SEVERITY_ORDER: LSPDiagnostic['severity'][] = ['error', 'warning', 'info', 'hint'];

const SEVERITY_COLORS: Record<LSPDiagnostic['severity'], string> = {
  error: 'text-red-400',
  warning: 'text-amber-400',
  info: 'text-blue-400',
  hint: 'text-muted',
};

const SEVERITY_DOT: Record<LSPDiagnostic['severity'], string> = {
  error: 'bg-red-500',
  warning: 'bg-amber-500',
  info: 'bg-blue-500',
  hint: 'bg-gray-400',
};

export function ProblemsPanel() {
  const [diagnostics, setDiagnostics] = useState<LSPDiagnostic[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeSeverity, setActiveSeverity] = useState<LSPDiagnostic['severity'] | null>(null);
  const [expandedFile, setExpandedFile] = useState<string | null>(null);
  const setActiveFile = useAppStore((s) => s.setActiveFile);

  const loadDiagnostics = useCallback(async () => {
    setLoading(true);
    try {
      const res = await lspDiagnostics('.');
      setDiagnostics(res.diagnostics || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDiagnostics(); }, [loadDiagnostics]);

  // Group by file
  const grouped = diagnostics.reduce<Record<string, LSPDiagnostic[]>>((acc, d) => {
    if (activeSeverity && d.severity !== activeSeverity) return acc;
    const file = d.file || 'unknown';
    if (!acc[file]) acc[file] = [];
    acc[file].push(d);
    return acc;
  }, {});

  const counts = {
    error: diagnostics.filter((d) => d.severity === 'error').length,
    warning: diagnostics.filter((d) => d.severity === 'warning').length,
    info: diagnostics.filter((d) => d.severity === 'info').length,
    hint: diagnostics.filter((d) => d.severity === 'hint').length,
  };

  const handleJump = (file: string, line: number) => {
    setActiveFile(file);
    // TODO: Also scroll to line in editor
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header with severity filter */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Problems</h2>
          <button onClick={loadDiagnostics} disabled={loading}
            className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
          >{loading ? '...' : 'Refresh'}</button>
        </div>
        <div className="flex gap-1">
          <button onClick={() => setActiveSeverity(null)}
            className={`px-2 py-0.5 text-[10px] rounded transition ${!activeSeverity ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'}`}
          >All ({diagnostics.length})</button>
          {(Object.keys(counts) as LSPDiagnostic['severity'][]).map((sev) => (
            <button key={sev} onClick={() => setActiveSeverity(activeSeverity === sev ? null : sev)}
              className={`px-2 py-0.5 text-[10px] rounded transition capitalize ${
                activeSeverity === sev ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'
              }`}
            >
              {sev} ({counts[sev]})
            </button>
          ))}
        </div>
      </div>

      {/* Diagnostic list */}
      <div className="flex-1 overflow-y-auto">
        {loading && diagnostics.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : Object.keys(grouped).length === 0 ? (
          <div className="text-xs text-muted text-center py-6">
            {activeSeverity ? `No ${activeSeverity} diagnostics.` : 'No problems detected.'}
          </div>
        ) : (
          Object.entries(grouped).map(([file, diags]) => (
            <div key={file}>
              <div
                onClick={() => setExpandedFile(expandedFile === file ? null : file)}
                className="px-3 py-1.5 bg-accent/5 text-[10px] font-medium text-muted cursor-pointer hover:bg-accent/10 transition flex items-center gap-1"
              >
                <span className="transform transition-transform" style={{ transform: expandedFile === file ? 'rotate(90deg)' : '' }}>▶</span>
                <span className="truncate">{file}</span>
                <span className="text-muted/60">({diags.length})</span>
              </div>
              {expandedFile === file && diags.map((d, i) => (
                <div
                  key={`${file}-${i}`}
                  onClick={() => handleJump(d.file, d.line)}
                  className="px-3 py-1.5 pl-6 border-b border-border/30 cursor-pointer hover:bg-accent/5 transition"
                >
                  <div className="flex items-start gap-1.5">
                    <span className={`inline-block h-1.5 w-1.5 rounded-full mt-1 shrink-0 ${SEVERITY_DOT[d.severity]}`} />
                    <div className="flex-1 min-w-0">
                      <div className={`text-[11px] ${SEVERITY_COLORS[d.severity]}`}>{d.message}</div>
                      <div className="text-[9px] text-muted mt-0.5">
                        Line {d.line}:{d.column}
                        {d.code && <span className="ml-1">({d.code})</span>}
                        {d.source && <span className="ml-1">[{d.source}]</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
