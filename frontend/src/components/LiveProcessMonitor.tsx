import React, { useState, useEffect, useRef } from 'react';
import {
  Terminal,
  ChevronDown,
  ChevronUp,
  Cpu,
  Shield,
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Zap,
  Maximize2,
  Minimize2,
  Filter,
} from 'lucide-react';
import type { ActivityEvent } from '../api/client';
import { fetchActivityEvents } from '../api/client';

const CATEGORY_COLORS: Record<string, { bg: string; text: string; badge: string }> = {
  LLM: {
    bg: 'bg-blue-950/60 border-blue-500/30',
    text: 'text-blue-400',
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  },
  GATEWAY: {
    bg: 'bg-amber-950/60 border-amber-500/30',
    text: 'text-amber-400',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  },
  DEPENDENCY: {
    bg: 'bg-emerald-950/60 border-emerald-500/30',
    text: 'text-emerald-400',
    badge: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  },
  SANDBOX: {
    bg: 'bg-purple-950/60 border-purple-500/30',
    text: 'text-purple-400',
    badge: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
  },
  INTAKE: {
    bg: 'bg-cyan-950/60 border-cyan-500/30',
    text: 'text-cyan-400',
    badge: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  },
  EVALUATION: {
    bg: 'bg-rose-950/60 border-rose-500/30',
    text: 'text-rose-400',
    badge: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
  },
  RUNTIME: {
    bg: 'bg-violet-950/60 border-violet-500/30',
    text: 'text-violet-400',
    badge: 'bg-violet-500/20 text-violet-300 border-violet-500/30',
  },
};

const STATUS_ICONS: Record<string, { icon: any; color: string }> = {
  success: { icon: CheckCircle, color: 'text-emerald-400' },
  warning: { icon: AlertTriangle, color: 'text-amber-400' },
  error: { icon: XCircle, color: 'text-rose-400' },
  security_alert: { icon: Shield, color: 'text-rose-400 animate-pulse' },
};

export const LiveProcessMonitor: React.FC = () => {
  const [isOpen, setIsOpen] = useState(true);
  const [isMaximized, setIsMaximized] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [expandedEventId, setExpandedEventId] = useState<string | null>(null);
  const [isLive, setIsLive] = useState(true);
  const lastTimestampRef = useRef<string | undefined>(undefined);
  const timerRef = useRef<number | null>(null);

  // Poll backend activity logs
  useEffect(() => {
    loadInitialEvents();
    startPolling();
    return () => {
      stopPolling();
    };
  }, []);

  const loadInitialEvents = async () => {
    try {
      const data = await fetchActivityEvents();
      if (data.length > 0) {
        setEvents(data.reverse());
        const maxTime = data.reduce((max, e) => (e.timestamp > max ? e.timestamp : max), '');
        lastTimestampRef.current = maxTime;
      }
    } catch (e) {
      console.error('Failed to load initial activity events:', e);
    }
  };

  const startPolling = () => {
    stopPolling();
    timerRef.current = window.setInterval(async () => {
      if (!isLive) return;
      try {
        const newEvents = await fetchActivityEvents(lastTimestampRef.current);
        if (newEvents.length > 0) {
          setEvents(prev => [...newEvents.reverse(), ...prev].slice(0, 250));
          const maxTime = newEvents.reduce((max, e) => (e.timestamp > max ? e.timestamp : max), '');
          if (maxTime) {
            lastTimestampRef.current = maxTime;
          }
        }
      } catch (e) {
        console.error('Error polling activity events:', e);
      }
    }, 2000);
  };

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const toggleEvent = (id: string) => {
    setExpandedEventId(prev => (prev === id ? null : id));
  };

  const clearLogs = () => {
    setEvents([]);
  };

  const filteredEvents = events.filter(e => {
    if (selectedCategory === 'ALL') return true;
    if (selectedCategory === 'ERRORS') return e.status === 'error' || e.status === 'warning';
    return e.category.toUpperCase() === selectedCategory;
  });

  return (
    <div className={`mt-8 border border-slate-800 rounded-2xl overflow-hidden glass-panel transition-all ${
      isMaximized ? 'fixed inset-4 z-50 shadow-2xl bg-slate-950/95 flex flex-col mt-0' : ''
    }`}>
      {/* Header */}
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-900/40 transition select-none flex-wrap gap-3"
      >
        <div className="flex items-center space-x-3">
          <div className="relative flex h-3 w-3">
            {isLive && (
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
            )}
            <span className={`relative inline-flex rounded-full h-3 w-3 ${isLive ? 'bg-cyan-500' : 'bg-slate-600'}`}></span>
          </div>
          <span className="text-xs font-mono font-bold tracking-wider text-slate-200 uppercase flex items-center gap-1.5">
            <Terminal className="w-3.5 h-3.5 text-cyan-400" />
            Live Process & Red-Teaming Monitor
          </span>
          <span className="px-1.5 py-0.5 text-[9.5px] font-mono rounded bg-slate-800 text-slate-400">
            {filteredEvents.length} events
          </span>
        </div>

        <div className="flex items-center space-x-2.5">
          {/* Category Filter Pills */}
          <div
            onClick={(e) => e.stopPropagation()}
            className="hidden sm:flex items-center space-x-1 bg-slate-900/80 p-0.5 rounded-lg border border-slate-800 text-[10px] font-mono font-bold"
          >
            {['ALL', 'ERRORS', 'INTAKE', 'LLM', 'SANDBOX', 'EVALUATION'].map(cat => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-2 py-0.5 rounded transition ${
                  selectedCategory === cat
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsLive(!isLive);
            }}
            className={`px-2.5 py-1 rounded text-[10px] font-mono font-bold border transition ${
              isLive
                ? 'bg-cyan-950/40 text-cyan-400 border-cyan-500/30'
                : 'bg-slate-900 text-slate-400 border-slate-700'
            }`}
          >
            {isLive ? 'PAUSE' : 'RESUME'}
          </button>

          <button
            onClick={(e) => {
              e.stopPropagation();
              clearLogs();
            }}
            className="px-2.5 py-1 rounded text-[10px] font-mono font-bold bg-slate-900 hover:bg-slate-800 text-slate-400 border border-slate-800 hover:text-slate-200 transition"
          >
            CLEAR
          </button>

          {/* Maximize / Expand Height Button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              setIsMaximized(!isMaximized);
              setIsOpen(true);
            }}
            title={isMaximized ? "Restore size" : "Expand to full viewport"}
            className="p-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700 hover:text-cyan-300 transition flex items-center gap-1 text-[10px] font-mono font-bold cursor-pointer"
          >
            {isMaximized ? (
              <>
                <Minimize2 className="w-3.5 h-3.5 text-cyan-400" />
                <span className="hidden md:inline">Restore</span>
              </>
            ) : (
              <>
                <Maximize2 className="w-3.5 h-3.5 text-cyan-400" />
                <span className="hidden md:inline">Fit Screen</span>
              </>
            )}
          </button>

          {isOpen ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
        </div>
      </div>

      {/* Content panel */}
      {isOpen && (
        <div className={`border-t border-slate-800/60 bg-slate-950/90 overflow-y-auto p-4 space-y-2 font-mono ${
          isMaximized ? 'flex-1 h-full' : 'max-h-[550px]'
        }`}>
          {filteredEvents.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              Waiting for backend processes to execute...
            </div>
          ) : (
            filteredEvents.map(event => {
              const cfg = CATEGORY_COLORS[event.category] || {
                bg: 'bg-slate-900/60 border-slate-800',
                text: 'text-slate-400',
                badge: 'bg-slate-800 text-slate-400 border-slate-700',
              };
              const statusInfo = STATUS_ICONS[event.status] || STATUS_ICONS.success;
              const StatusIcon = statusInfo.icon;
              const isExpanded = expandedEventId === event.id;

              return (
                <div
                  key={event.id}
                  className={`border rounded-xl transition duration-200 ${
                    isExpanded ? cfg.bg : 'bg-slate-950/40 border-slate-900/60 hover:bg-slate-900/20'
                  }`}
                >
                  {/* Row summary */}
                  <div
                    onClick={() => toggleEvent(event.id)}
                    className="p-3 flex items-center justify-between text-xs cursor-pointer select-none gap-3 flex-wrap"
                  >
                    <div className="flex items-center space-x-2.5 min-w-0 flex-1">
                      <span className="text-[10px] text-slate-500 font-mono shrink-0">
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                      <span className={`px-2 py-0.5 rounded-lg text-[9px] font-mono font-bold border shrink-0 ${cfg.badge}`}>
                        {event.category}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[9px] font-mono uppercase bg-slate-900 text-slate-400 shrink-0">
                        {event.action}
                      </span>
                      <span className={`font-medium text-[11px] truncate ${
                        event.status === 'error' ? 'text-rose-300' : event.status === 'warning' ? 'text-amber-300' : 'text-slate-200'
                      }`}>
                        {event.detail}
                      </span>
                    </div>

                    <div className="flex items-center space-x-2.5 font-mono text-[10px] shrink-0">
                      {event.duration_ms !== null && event.duration_ms !== undefined && (
                        <span className="text-slate-400 flex items-center gap-0.5">
                          <Zap className="w-3 h-3 text-amber-400" />
                          {event.duration_ms.toFixed(0)}ms
                        </span>
                      )}
                      <StatusIcon className={`w-3.5 h-3.5 ${statusInfo.color}`} />
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 border-t border-slate-800/40 space-y-3">
                      {event.request_summary && (
                        <div className="space-y-1">
                          <div className="text-[9.5px] font-mono text-slate-500 uppercase tracking-wider">REQUEST PAYLOAD / DETAILS</div>
                          <pre className="p-3 rounded-lg bg-slate-950 border border-slate-900 text-[10.5px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
                            {event.request_summary}
                          </pre>
                        </div>
                      )}
                      {event.response_summary && (
                        <div className="space-y-1">
                          <div className="text-[9.5px] font-mono text-slate-500 uppercase tracking-wider">RESPONSE / ERROR TRACEBACK</div>
                          <pre className="p-3 rounded-lg bg-slate-950 border border-slate-900 text-[10.5px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap">
                            {event.response_summary}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
