import React, { useState, useEffect } from 'react';
import { FileCode, BookOpen, Layers, CheckCircle2 } from 'lucide-react';

interface CodeFileInspectorProps {
  files: Record<string, string>;
  metadata?: Record<string, string>;
  onRemove?: (fname: string) => void;
}

const getLanguage = (fname: string) => {
  if (fname.endsWith('.py')) return 'Python';
  if (fname.endsWith('.ts')) return 'TypeScript';
  if (fname.endsWith('.js')) return 'JavaScript';
  if (fname.endsWith('.json')) return 'JSON';
  if (fname.endsWith('.yaml') || fname.endsWith('.yml')) return 'YAML';
  if (fname.endsWith('.md')) return 'Markdown';
  return 'Text';
};

export const CodeFileInspector: React.FC<CodeFileInspectorProps> = ({ files, metadata, onRemove }) => {
  const fnames = Object.keys(files);
  const [activeFile, setActiveFile] = useState(fnames[0] ?? '');

  useEffect(() => {
    if (!files[activeFile] && fnames.length > 0) {
      setActiveFile(fnames[0]);
    }
  }, [files, activeFile, fnames]);

  if (fnames.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Metadata Banner if available */}
      {metadata && Object.keys(metadata).length > 0 && (
        <div className="p-4 rounded-xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-indigo-500/30 text-xs space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <span className="font-bold text-slate-100 text-sm">{metadata.title || 'Demonstration Agent'}</span>
              {metadata.framework && (
                <span className="px-2 py-0.5 text-[10px] font-mono rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  {metadata.framework}
                </span>
              )}
            </div>
            {metadata.author && (
              <span className="text-[11px] text-slate-400 font-mono">by @{metadata.author}</span>
            )}
          </div>

          {metadata.description && (
            <p className="text-slate-300 text-xs leading-relaxed">{metadata.description}</p>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            {metadata.language && (
              <span className="px-2 py-0.5 text-[10px] rounded bg-slate-800 text-slate-300">Lang: {metadata.language}</span>
            )}
            {metadata.llm && (
              <span className="px-2 py-0.5 text-[10px] rounded bg-slate-800 text-indigo-300">Model: {metadata.llm}</span>
            )}
            {metadata.industry && (
              <span className="px-2 py-0.5 text-[10px] rounded bg-slate-800 text-emerald-300">Domain: {metadata.industry}</span>
            )}
          </div>
        </div>
      )}

      {/* Code Inspector Frame */}
      <div className="rounded-xl border border-slate-700 bg-slate-950 shadow-inner overflow-hidden">
        {/* File Tabs */}
        <div className="flex overflow-x-auto border-b border-slate-800 bg-slate-900/90">
          {fnames.map((fname) => (
            <div key={fname} className="flex items-center shrink-0">
              <button
                onClick={() => setActiveFile(fname)}
                className={`px-3 py-2 text-[11px] font-mono border-r border-slate-800 flex items-center space-x-2 transition ${
                  activeFile === fname
                    ? 'bg-slate-950 text-cyan-300 border-b-2 border-b-cyan-400 font-bold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    fname.endsWith('.py')
                      ? 'bg-blue-400'
                      : fname.endsWith('.json')
                      ? 'bg-amber-400'
                      : fname.endsWith('.yaml') || fname.endsWith('.yml')
                      ? 'bg-emerald-400'
                      : fname.endsWith('.md')
                      ? 'bg-purple-400'
                      : 'bg-slate-400'
                  }`}
                />
                <span>{fname}</span>
              </button>
              {onRemove && (
                <button
                  onClick={() => onRemove(fname)}
                  className="px-2 py-2 text-slate-500 hover:text-rose-400 text-xs border-r border-slate-800 transition"
                  title="Remove file"
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <div className="ml-auto px-3 py-2 text-[10px] text-slate-500 font-mono flex items-center space-x-2">
            <span>{getLanguage(activeFile)}</span>
            <span>·</span>
            <span>{(files[activeFile]?.length ?? 0).toLocaleString()} chars</span>
          </div>
        </div>

        {/* File Content Body */}
        <div className="relative bg-slate-950">
          <pre className="p-4 text-[11px] font-mono text-cyan-200 leading-relaxed overflow-x-auto max-h-80 overflow-y-auto whitespace-pre">
            <code>{files[activeFile] ?? ''}</code>
          </pre>
          <span className="absolute bottom-2 right-3 text-[9px] text-slate-500 font-mono bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
            {(files[activeFile] ?? '').split('\n').length} lines
          </span>
        </div>
      </div>
    </div>
  );
};
