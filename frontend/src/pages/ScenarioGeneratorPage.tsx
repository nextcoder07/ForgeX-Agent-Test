import React, { useState, useEffect } from 'react';
import { fetchAgents, fetchStrategyPlan, generateScenarios, fetchScenarioLibrary, fetchCoverageReport } from '../api/client';
import type { AgentRecord, StrategyPlan, Scenario, CoverageGapReport } from '../api/client';
import { ScenarioStrategyView } from '../components/ScenarioStrategyView';
import { ScenarioLibraryView } from '../components/ScenarioLibraryView';
import { CoverageGapWidget } from '../components/CoverageGapWidget';
import { Layers, RefreshCw, Sparkles } from 'lucide-react';
import type { PageId } from '../components/Navbar';

interface ScenarioGeneratorPageProps {
  onNavigate: (page: PageId) => void;
}

export const ScenarioGeneratorPage: React.FC<ScenarioGeneratorPageProps> = ({ onNavigate }) => {
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [strategy, setStrategy] = useState<StrategyPlan | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [coverage, setCoverage] = useState<CoverageGapReport | null>(null);
  const [loadingStrategy, setLoadingStrategy] = useState(false);
  const [loadingGenerate, setLoadingGenerate] = useState(false);
  const [targetCount, setTargetCount] = useState(20);

  useEffect(() => {
    fetchAgents().then((list) => {
      setAgents(list);
      if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, []);

  useEffect(() => {
    if (!selectedAgentId) return;
    fetchScenarioLibrary(selectedAgentId).then(setScenarios).catch(console.error);
  }, [selectedAgentId]);

  const handleLoadStrategy = async () => {
    if (!selectedAgentId) return;
    setLoadingStrategy(true);
    try {
      const [plan, cov] = await Promise.all([
        fetchStrategyPlan(selectedAgentId),
        fetchCoverageReport(selectedAgentId),
      ]);
      setStrategy(plan);
      setCoverage(cov);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingStrategy(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedAgentId) return;
    setLoadingGenerate(true);
    try {
      const newScenarios = await generateScenarios(selectedAgentId, targetCount);
      setScenarios((prev) => {
        const ids = new Set(prev.map(s => s.id));
        return [...prev, ...newScenarios.filter(s => !ids.has(s.id))];
      });
      const cov = await fetchCoverageReport(selectedAgentId);
      setCoverage(cov);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingGenerate(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100">Scenario Intelligence Engine</h1>
        <p className="text-sm text-slate-400 mt-1">
          Auto-generate 8-category adversarial and normal test suites for any agent. Every scenario passes a critic review before entering the library.
        </p>
      </div>

      {/* Agent + Controls */}
      <div className="p-5 rounded-2xl glass-panel border border-slate-800 flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-48">
          <label className="text-xs font-semibold text-slate-400 block mb-1">Target Agent:</label>
          <select
            value={selectedAgentId}
            onChange={(e) => setSelectedAgentId(e.target.value)}
            className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition"
          >
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.display_name || a.name} · registered: {a.name} · {a.version_label}
              </option>
            ))}
            {agents.length === 0 && <option>No agents yet — use Intake page</option>}
          </select>
        </div>

        <div className="flex items-end space-x-2">
          <div>
            <label className="text-xs font-semibold text-slate-400 block mb-1">Target Count:</label>
            <input
              type="number"
              min={5}
              max={100}
              value={targetCount}
              onChange={(e) => setTargetCount(Number(e.target.value))}
              className="w-20 p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500 transition text-center"
            />
          </div>

          <button
            onClick={handleLoadStrategy}
            disabled={loadingStrategy || !selectedAgentId}
            className="px-4 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-cyan-300 font-bold text-xs flex items-center space-x-1.5 transition disabled:opacity-50"
          >
            {loadingStrategy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
            <span>Load Strategy Plan</span>
          </button>

          <button
            onClick={handleGenerate}
            disabled={loadingGenerate || !selectedAgentId}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-400 hover:to-rose-500 text-slate-100 font-bold text-xs flex items-center space-x-1.5 transition disabled:opacity-50 shadow-lg shadow-cyan-500/20"
          >
            {loadingGenerate ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Generating & Critiquing...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Generate {targetCount} Scenarios</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Strategy Plan View */}
      {strategy && (
        <ScenarioStrategyView strategy={strategy} isGenerating={loadingGenerate} />
      )}

      {/* Coverage Gap Widget */}
      {coverage && (
        <CoverageGapWidget report={coverage} onGenerateTargeted={handleGenerate} />
      )}

      {/* Scenario Library */}
      {scenarios.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-100">
              Scenario Library ({scenarios.length} scenarios)
            </h2>
          </div>
          <ScenarioLibraryView
            scenarios={scenarios}
            onRunSelected={(ids) => {
              console.log('Run selected scenarios:', ids);
              onNavigate('evaluations');
            }}
          />
        </div>
      )}

      {scenarios.length === 0 && !loadingGenerate && (
        <div className="py-16 text-center space-y-3">
          <Layers className="w-12 h-12 mx-auto text-slate-700" />
          <p className="text-sm text-slate-400">No scenarios yet. Select an agent and click Generate.</p>
        </div>
      )}
    </div>
  );
};
