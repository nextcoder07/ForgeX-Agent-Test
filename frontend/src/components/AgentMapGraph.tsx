import React, { useState } from 'react';
import type { GraphNode, GraphEdge } from '../api/client';
import { Cpu, Wrench, Database, Globe, Network, ShieldAlert, Sparkles, Layers } from 'lucide-react';

interface AgentMapGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const AgentMapGraph: React.FC<AgentMapGraphProps> = ({ nodes, edges }) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const modelAndPlanningNodes = nodes.filter(n => n.type === 'agent' || n.type === 'subagent');
  const toolNodes = nodes.filter(n => n.type === 'tool');
  const memoryAndRagNodes = nodes.filter(n => n.type === 'memory' || n.type === 'database');
  const backendNodes = nodes.filter(n => n.type === 'api' || n.type === 'backend');

  return (
    <div className="p-6 rounded-2xl glass-panel border border-slate-800 bg-slate-950/90 shadow-xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <Network className="w-5 h-5 text-slate-300" />
            <h3 className="text-base font-bold text-slate-100">Discovered Architecture & Execution Flow Map</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Auto-reconstructed interactive topology: Model Roles & Planning → Tool Gateway → Memory/RAG → External Services.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono">
          <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-slate-400"></span><span className="text-slate-400">Model Role</span></span>
          <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-indigo-400"></span><span className="text-slate-400">Planning</span></span>
          <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-amber-400"></span><span className="text-slate-400">Memory/RAG</span></span>
          <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-rose-500"></span><span className="text-slate-400">Critical Tool</span></span>
          <span className="flex items-center space-x-1"><span className="w-2 h-2 rounded-full bg-emerald-400"></span><span className="text-slate-400">External Gateway</span></span>
        </div>
      </div>

      {/* 4-Tier Subsystem Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800 relative">
        {/* Tier 1: Model Roles & Planning */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono uppercase text-slate-400 font-bold block border-b border-slate-800 pb-1">
            1. Model Roles & Planning ({modelAndPlanningNodes.length})
          </span>
          <div className="space-y-2">
            {modelAndPlanningNodes.map(node => (
              <div
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`p-3 rounded-xl border cursor-pointer transition-all ${
                  selectedNode?.id === node.id
                    ? 'bg-slate-800 border-slate-700 text-slate-100'
                    : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                }`}
              >
                <div className="flex items-center space-x-2">
                  {node.label.includes('Planning') ? (
                    <Layers className="w-4 h-4 text-indigo-400 shrink-0" />
                  ) : (
                    <Cpu className="w-4 h-4 text-cyan-400 shrink-0" />
                  )}
                  <span className="font-bold text-xs truncate">{node.label}</span>
                </div>
                <p className="text-[11px] text-slate-400 mt-1 line-clamp-2">{node.details}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Tier 2: Extracted Tools */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono uppercase text-amber-400 font-bold block border-b border-slate-800 pb-1">
            2. Tools & Actions ({toolNodes.length})
          </span>
          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {toolNodes.length > 0 ? (
              toolNodes.map(node => {
                const isCrit = node.risk === 'critical';
                const isHigh = node.risk === 'high';
                const isMed = node.risk === 'medium';

                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-2.5 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                      selectedNode?.id === node.id
                        ? 'bg-slate-800 border-cyan-400 text-cyan-200'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                    }`}
                  >
                    <div className="flex items-center space-x-2 truncate">
                      <Wrench className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="font-mono text-xs font-semibold truncate">{node.label}</span>
                    </div>
                    <span className={`px-1.5 py-0.5 text-[9px] uppercase font-bold rounded shrink-0 ${
                      isCrit ? 'bg-rose-950 text-rose-300 border border-rose-500/30' :
                      isHigh ? 'bg-amber-950 text-amber-300 border border-amber-500/30' :
                      isMed ? 'bg-indigo-950 text-indigo-300 border border-indigo-500/30' :
                      'bg-slate-800 text-slate-400'
                    }`}>
                      {node.risk}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="p-3 text-[11px] text-slate-500 bg-slate-900/40 rounded-lg border border-slate-800/40">
                Pure LLM Agent (No tools declared)
              </div>
            )}
          </div>
        </div>

        {/* Tier 3: Memory & Context / RAG */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono uppercase text-emerald-400 font-bold block border-b border-slate-800 pb-1">
            3. Memory & RAG ({memoryAndRagNodes.length})
          </span>
          <div className="space-y-2">
            {memoryAndRagNodes.length > 0 ? (
              memoryAndRagNodes.map(node => (
                <div
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    selectedNode?.id === node.id
                      ? 'bg-emerald-950/60 border-emerald-400 text-emerald-200'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                    <span className="font-bold text-xs truncate">{node.label}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{node.details}</p>
                </div>
              ))
            ) : (
              <div className="p-3 text-[11px] text-slate-500 bg-slate-900/40 rounded-lg border border-slate-800/40">
                Stateless Request-Response Scope
              </div>
            )}
          </div>
        </div>

        {/* Tier 4: External Services */}
        <div className="space-y-3">
          <span className="text-[10px] font-mono uppercase text-indigo-400 font-bold block border-b border-slate-800 pb-1">
            4. External Gateways ({backendNodes.length})
          </span>
          <div className="space-y-2">
            {backendNodes.length > 0 ? (
              backendNodes.map(node => (
                <div
                  key={node.id}
                  onClick={() => setSelectedNode(node)}
                  className={`p-3 rounded-xl border cursor-pointer transition-all ${
                    selectedNode?.id === node.id
                      ? 'bg-indigo-950/60 border-indigo-400 text-indigo-200'
                      : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-300'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <Globe className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                    <span className="font-bold text-xs truncate">{node.label}</span>
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">{node.details}</p>
                </div>
              ))
            ) : (
              <div className="p-3 text-[11px] text-slate-500 bg-slate-900/40 rounded-lg border border-slate-800/40">
                No external API dependencies
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Selected Node Inspector Drawer */}
      {selectedNode && (
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-cyan-300 font-bold font-mono">Inspect Node: {selectedNode.label}</span>
            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-400">
              Type: {selectedNode.type} · Risk: {selectedNode.risk}
            </span>
          </div>
          <p className="text-slate-400">{selectedNode.details || 'No additional parameters provided.'}</p>
        </div>
      )}
    </div>
  );
};
