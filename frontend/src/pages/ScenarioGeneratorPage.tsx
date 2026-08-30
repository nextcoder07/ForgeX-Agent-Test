import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { fetchAgents, fetchStrategyPlan, generateScenarios, fetchScenarioLibrary, fetchCoverageReport } from '../api/client';
import type { AgentRecord, StrategyPlan, Scenario, CoverageGapReport } from '../api/client';
import { ScenarioStrategyView } from '../components/ScenarioStrategyView';
import { ScenarioLibraryView } from '../components/ScenarioLibraryView';
import { CoverageGapWidget } from '../components/CoverageGapWidget';
import { LiveAttackPage } from './LiveAttackPage';
import { Layers, RefreshCw, Sparkles, ArrowRight, Radio, Flame } from 'lucide-react';
import { LiveProcessMonitor } from '../components/LiveProcessMonitor';

interface ScenarioGeneratorPageProps {
}

export const ScenarioGeneratorPage: React.FC<{}> = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const scenarioTab = (searchParams.get('tab') || 'generate') as 'generate' | 'adversarial';
  const agentIdFromUrl = searchParams.get('agentId') || '';

  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState('');
  const [strategy, setStrategy] = useState<StrategyPlan | null>(null);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [coverage, setCoverage] = useState<CoverageGapReport | null>(null);
  const [loadingStrategy, setLoadingStrategy] = useState(false);
  const [loadingGenerate, setLoadingGenerate] = useState(false);
  const [targetCount, setTargetCount] = useState(20);

  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({
    normal: 2,
    edge: 2,
    recovery: 1,
    adversarial: 2,
    safety: 2,
    security: 2,
    stress: 1,
    chaos: 1,
    destructive_guardrail: 1,
  });
  const [useCategoryCounts, setUseCategoryCounts] = useState(false);

  useEffect(() => {
    fetchAgents().then((list) => {
      setAgents(list);
      if (agentIdFromUrl && list.some(a => a.id === agentIdFromUrl)) {
        setSelectedAgentId(agentIdFromUrl);
      } else if (list.length > 0) {
        setSelectedAgentId(list[0].id);
      }
    });
  }, [agentIdFromUrl]);

  useEffect(() => {
    if (!selectedAgentId) return;
    fetchScenarioLibrary(selectedAgentId).then(setScenarios).catch(console.error);
    fetchCoverageReport(selectedAgentId).then(setCoverage).catch(console.error);
  }, [selectedAgentId]);

  const handleLoadStrategy = async () => {
    if (!selectedAgentId) return;
    setLoadingStrategy(true);
    try {
      const countsToUse = useCategoryCounts ? categoryCounts : undefined;
      const countToRequest = useCategoryCounts ? Object.values(categoryCounts).reduce((a, b) => a + b, 0) : targetCount;
      const [plan, cov] = await Promise.all([
        fetchStrategyPlan(selectedAgentId, countToRequest, countsToUse),
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
      const countsToUse = useCategoryCounts ? categoryCounts : undefined;
      const countToRequest = useCategoryCounts ? Object.values(categoryCounts).reduce((a, b) => a + b, 0) : targetCount;
      
      const newScenarios = await generateScenarios(selectedAgentId, countToRequest, undefined, undefined, countsToUse);
      if (Array.isArray(newScenarios) && newScenarios.length > 0) {
        setScenarios(newScenarios);
      }
      const [updatedScenarios, cov] = await Promise.all([
        fetchScenarioLibrary(selectedAgentId),
        fetchCoverageReport(selectedAgentId),
      ]);
      if (Array.isArray(updatedScenarios) && updatedScenarios.length > 0) {
        setScenarios(updatedScenarios);
      }
      setCoverage(cov);
    } catch (e) {
      console.error('Scenario generation failed:', e);
    } finally {
      setLoadingGenerate(false);
    }
  };

  const updateCatCount = (cat: string, delta: number) => {
    setCategoryCounts(prev => ({
      ...prev,
      [cat]: Math.max(0, (prev[cat] || 0) + delta)
    }));
  };

  const totalCustomCount = Object.values(categoryCounts).reduce((a, b) => a + b, 0);

  return (
    <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-4 sm:space-y-5">
      <div>
        <h1 className="text-xl sm:text-2xl font-extrabold text-slate-100">Scenarios</h1>
        <p className="text-xs sm:text-sm text-slate-300 mt-1">
          Generate test suites, browse your library, and run adversarial red-teaming.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex items-center space-x-1 border-b border-slate-800">
        {([
          { id: 'generate', label: 'Generate & Library', icon: Sparkles },
          { id: 'adversarial', label: 'Adversarial / Live Attack (Disabled)', icon: Flame },
        ] as const).map(t => (
          <button
            key={t.id}
            onClick={() => setSearchParams({ tab: t.id })}
            className={`flex items-center space-x-1.5 px-4 py-2 text-xs font-semibold rounded-t-lg border-b-2 transition-all cursor-pointer ${
              scenarioTab === t.id
                ? 'border-cyan-400 text-cyan-300 bg-slate-900/40'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/20'
            }`}
          >
            <t.icon className="w-3.5 h-3.5" />
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* Adversarial tab */}
      {scenarioTab === 'adversarial' && <LiveAttackPage />}

      {/* Generate + Library tab */}
      {scenarioTab === 'generate' && <>

      <div className="p-4 sm:p-5 rounded-2xl glass-panel border border-slate-700/80 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex-1 min-w-48">
            <label className="text-xs font-semibold text-slate-300 block mb-1">Target Agent:</label>
            <select
              value={selectedAgentId}
              onChange={(e) => setSelectedAgentId(e.target.value)}
              className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-700 text-cyan-300 font-mono text-xs focus:outline-none focus:border-cyan-500 transition"
            >
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.display_name || a.name} · registered: {a.name} · {a.version_label}
                </option>
              ))}
              {agents.length === 0 && <option>No agents yet — use Intake page</option>}
            </select>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setUseCategoryCounts(!useCategoryCounts)}
              className={`px-3 py-2 rounded-xl text-xs font-mono font-bold border transition ${
                useCategoryCounts
                  ? 'bg-cyan-950/60 text-cyan-300 border-cyan-500/50 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
              }`}
            >
              {useCategoryCounts ? '✓ Custom Counts by Category' : '⚙ Customize Category Counts'}
            </button>

            {!useCategoryCounts && (
              <div>
                <label className="text-[10px] font-mono text-slate-400 block mb-0.5">Target Count:</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={targetCount}
                  onChange={(e) => setTargetCount(Number(e.target.value))}
                  className="w-20 p-2 rounded-xl bg-slate-900 border border-slate-700 text-slate-100 font-mono text-xs focus:outline-none focus:border-cyan-500 transition text-center"
                />
              </div>
            )}

            <button
              onClick={handleLoadStrategy}
              disabled={loadingStrategy || !selectedAgentId}
              className="px-3.5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-700 text-cyan-300 font-bold text-xs flex items-center space-x-1.5 transition disabled:opacity-50"
            >
              {loadingStrategy ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Layers className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">Strategy Plan</span>
            </button>

            <button
              onClick={handleGenerate}
              disabled={loadingGenerate || !selectedAgentId || (useCategoryCounts && totalCustomCount === 0)}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 via-indigo-600 to-rose-600 hover:from-cyan-400 hover:to-rose-500 text-slate-100 font-bold text-xs flex items-center space-x-1.5 transition disabled:opacity-50 shadow-lg shadow-cyan-500/20 cursor-pointer"
            >
              {loadingGenerate ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Generating ({useCategoryCounts ? totalCustomCount : targetCount})...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Generate +{useCategoryCounts ? totalCustomCount : targetCount} Scenarios</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Custom Category Count Matrix */}
        {useCategoryCounts && (
          <div className="pt-3 border-t border-slate-800 space-y-2">
            <div className="text-[11px] font-mono font-bold text-slate-300 uppercase tracking-wider flex items-center justify-between">
              <span>Select Count for Each Category (Batch Total: {totalCustomCount}):</span>
              <span className="text-slate-400 font-normal normal-case text-[11px]">
                Currently in agent library: <b className="text-cyan-300">{scenarios.length} scenarios</b>
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-2">
              {['normal', 'edge', 'recovery', 'adversarial', 'safety', 'security', 'stress', 'chaos', 'destructive_guardrail'].map(cat => {
                const count = categoryCounts[cat] || 0;
                const label = cat === 'destructive_guardrail' ? 'DESTRUCTIVE' : cat;
                return (
                  <div key={cat} className="p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-col items-center space-y-1.5" title={cat}>
                    <span className="text-[10px] font-mono font-bold uppercase text-slate-300 truncate max-w-full">{label}</span>
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => updateCatCount(cat, -1)}
                        className="w-6 h-6 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-mono text-xs flex items-center justify-center font-bold"
                      >
                        -
                      </button>
                      <span className="font-mono text-xs font-bold text-cyan-300 w-5 text-center">{count}</span>
                      <button
                        onClick={() => updateCatCount(cat, 1)}
                        className="w-6 h-6 rounded bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-mono text-xs flex items-center justify-center font-bold"
                      >
                        +
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
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
        <div className="space-y-4">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <h2 className="text-base font-bold text-slate-100">
              Scenario Library ({scenarios.filter(s => ['VALIDATED', 'EXECUTABLE', 'GENERATED'].includes(s.validation_status || '')).length} ready
              {scenarios.filter(s => s.validation_status === 'FAILED_GENERATION').length > 0 && (
                <span className="text-rose-400 font-normal text-sm ml-2">
                  · {scenarios.filter(s => s.validation_status === 'FAILED_GENERATION').length} could not be generated
                </span>
              )}
              )
            </h2>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => navigate(`/setup?agentId=${selectedAgentId}`)}
                className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 text-xs font-bold font-mono transition"
              >
                3. Setup →
              </button>
              <button
                onClick={() => navigate(`/executions?agentId=${selectedAgentId}`)}
                className="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-bold font-mono flex items-center space-x-1.5 shadow-md shadow-indigo-500/20 transition"
              >
                <Radio className="w-3.5 h-3.5" />
                <span>4. Run Execution Sandbox →</span>
              </button>
            </div>
          </div>
          <ScenarioLibraryView
            scenarios={scenarios}
            onRunSelected={(ids) => {
              console.log('Run selected scenarios:', ids);
              navigate(`/executions?agentId=${selectedAgentId}`);
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

      {/* Live Process Monitor */}
      <LiveProcessMonitor />
      </>}
    </div>
  );
};
