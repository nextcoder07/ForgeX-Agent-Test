import React, { useEffect, useState } from 'react';
import type { Scenario } from '../api/client';
import { Layers, ShieldCheck, CheckCircle2, AlertTriangle, Filter, Search, Play, Zap } from 'lucide-react';

interface ScenarioLibraryViewProps {
  scenarios: Scenario[];
  onRunSelected?: (selectedIds: string[]) => void;
  isRunning?: boolean;
}

export const ScenarioLibraryView: React.FC<ScenarioLibraryViewProps> = ({
  scenarios,
  onRunSelected,
  isRunning = false,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Failed-generation placeholders cannot be executed; reviewed scenarios remain runnable.
  const runnableScenarios = scenarios.filter(s => s.validation_status !== 'FAILED_GENERATION');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    new Set(runnableScenarios.map(s => s.id))
  );

  useEffect(() => {
    setSelectedIds(new Set(runnableScenarios.map(s => s.id)));
  }, [scenarios]);

  const categories = ['all', 'normal', 'edge', 'recovery', 'adversarial', 'safety', 'security', 'stress', 'chaos'];

  const filteredScenarios = scenarios.filter((sc) => {
    const matchesCat = selectedCategory === 'all' || sc.category === selectedCategory;
    const matchesSearch =
      sc.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sc.purpose.toLowerCase().includes(searchQuery.toLowerCase()) ||
      sc.id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const toggleSelectAll = () => {
    if (selectedIds.size === runnableScenarios.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(runnableScenarios.map(s => s.id)));
    }
  };

  const toggleSelectOne = (id: string, isRunnable: boolean) => {
    if (!isRunnable) return;
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="p-4 rounded-2xl glass-panel border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Search and Category Filter */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          <div className="relative flex-1 md:w-64">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search scenarios..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div className="flex items-center space-x-1 overflow-x-auto pb-1 md:pb-0">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-mono uppercase font-bold transition ${
                  selectedCategory === cat
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        {/* Batch Actions */}
        <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
          <button
            onClick={toggleSelectAll}
            disabled={runnableScenarios.length === 0}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 transition"
          >
            {runnableScenarios.length > 0 && selectedIds.size === runnableScenarios.length
              ? 'Deselect All'
              : `Select All (${runnableScenarios.length})`}
          </button>

          {onRunSelected && (
            <button
              onClick={() => onRunSelected(Array.from(selectedIds))}
              disabled={isRunning || selectedIds.size === 0}
              className="px-5 py-1.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-600 hover:to-rose-700 text-slate-100 font-bold text-xs shadow-lg shadow-cyan-500/20 flex items-center space-x-2 transition disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Run Selected ({selectedIds.size})</span>
            </button>
          )}
        </div>
      </div>

      {/* Scenario Table / Cards */}
      <div className="max-h-[calc(100vh-18rem)] overflow-y-auto scrollbar-thin rounded-2xl border border-slate-800/50 p-1">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {filteredScenarios.map((sc) => {
            const isFailedGen = sc.validation_status === 'FAILED_GENERATION';
            const isRunnable = !isFailedGen;
            const isSelected = selectedIds.has(sc.id);

            return (
              <div
                key={sc.id}
                onClick={() => toggleSelectOne(sc.id, isRunnable)}
                className={`p-4 rounded-xl border transition-all flex flex-col justify-between space-y-3 ${
                  isFailedGen
                    ? 'bg-slate-950/30 border-rose-950/40 cursor-not-allowed opacity-50'
                    : isSelected
                    ? 'bg-slate-900/90 border-cyan-500/50 shadow-md shadow-cyan-500/10 cursor-pointer'
                    : 'bg-slate-950/70 border-slate-800 hover:border-slate-700 opacity-70 cursor-pointer'
                }`}
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      {!isFailedGen && (
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onClick={(event) => event.stopPropagation()}
                          onChange={() => toggleSelectOne(sc.id, isRunnable)}
                          className="rounded border-slate-700 text-cyan-500 focus:ring-0 cursor-pointer"
                        />
                      )}
                      <span className="font-mono text-[10px] text-slate-400">{sc.id}</span>
                    </div>
                    <span
                      className={`px-2 py-0.5 text-[9px] font-mono uppercase font-bold rounded ${
                        isFailedGen
                          ? 'bg-slate-800 text-slate-400 border border-slate-700'
                          : sc.category === 'safety' || sc.category === 'security'
                          ? 'bg-rose-950 text-rose-300 border border-rose-500/30'
                          : sc.category === 'recovery' || sc.category === 'chaos'
                          ? 'bg-indigo-950 text-indigo-300 border border-indigo-500/30'
                          : 'bg-cyan-950 text-cyan-300 border border-cyan-500/30'
                      }`}
                    >
                      {sc.category}
                    </span>
                  </div>

                  <h4 className="text-xs font-bold text-slate-100 line-clamp-1">{sc.title}</h4>
                  <p className="text-[11px] text-slate-300 line-clamp-2 leading-relaxed">{sc.purpose}</p>

                  {/* 1. Test Input / User Prompt Preview */}
                  {(() => {
                    const promptText = sc.user_messages && sc.user_messages.length > 0
                      ? sc.user_messages[0]
                      : sc.invocation?.command || (sc.invocation?.body ? JSON.stringify(sc.invocation.body) : null);
                    if (!promptText) return null;
                    return (
                      <div className="p-2 rounded-lg bg-slate-950 border border-slate-850 space-y-0.5 font-mono text-[10.5px]">
                        <span className="text-[9px] uppercase font-bold text-slate-400 block tracking-wider">
                          {sc.interface_type === 'CLI' ? 'EXECUTION COMMAND' : 'TEST INPUT / PROMPT'}:
                        </span>
                        <p className="text-cyan-300 truncate">{promptText}</p>
                      </div>
                    );
                  })()}

                  {/* 2. Key Assertions & Fault Injections */}
                  <div className="space-y-1 pt-1">
                    {sc.fault_injections && sc.fault_injections.length > 0 && (
                      <div className="flex items-center space-x-1.5 text-[9.5px] font-mono text-amber-300 bg-amber-950/30 px-2 py-1 rounded border border-amber-500/20">
                        <Zap className="w-3 h-3 text-amber-400 shrink-0" />
                        <span className="truncate">Fault: {sc.fault_injections[0].fault_type} on `{sc.fault_injections[0].target_tool}`</span>
                      </div>
                    )}

                    {sc.assertions && sc.assertions.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {sc.assertions.slice(0, 2).map((a, aIdx) => (
                          <span
                            key={aIdx}
                            className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold border ${
                              a.assertion_type.includes('NOT') || a.assertion_type.includes('SECURITY')
                                ? 'bg-rose-950/40 text-rose-300 border-rose-500/30'
                                : 'bg-slate-850 text-slate-300 border-slate-700'
                            }`}
                          >
                            {a.assertion_type}: <code className="text-white">{a.target || a.expected_value || 'pass'}</code>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] font-mono">
                  <span className="text-slate-400 truncate max-w-[170px]">
                    {sc.target_failure_surface || (sc.required_capabilities && sc.required_capabilities.length > 0 ? `Cap: ${sc.required_capabilities[0]}` : `Scope: ${sc.category.toUpperCase()}`)}
                  </span>
                  <span
                    className={`flex items-center space-x-1 font-bold shrink-0 ${
                      sc.validation_status === 'VALIDATED' ? 'text-emerald-400' : isFailedGen ? 'text-rose-500' : 'text-amber-400'
                    }`}
                  >
                    {isFailedGen ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                    <span>{sc.validation_status === 'VALIDATED' ? 'SPEC_VALIDATED' : sc.validation_status}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
