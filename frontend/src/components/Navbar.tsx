import React, { useState } from 'react';
import {
  Activity,
  Layers,
  Sparkles,
  Zap,
  Flame,
  BarChart3,
  GitCompare,
  CheckCircle2,
  Cpu,
  ShieldCheck,
  Radio,
  Wrench,
  Menu,
  X,
  ChevronRight,
} from 'lucide-react';

export type PageId =
  | 'dashboard'
  | 'intake'
  | 'dependencies'
  | 'agents'
  | 'scenarios'
  | 'executions'
  | 'evaluations'
  | 'failures'
  | 'scorecard'
  | 'live-attack'
  | 'calibration'
  | 'pipeline'
  | 'fix-agent';

interface NavbarProps {
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activePage, onNavigate }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }>; category?: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'intake', label: 'Bring Your Agent', icon: Sparkles },
    { id: 'dependencies', label: 'Dep Setup', icon: Layers },
    { id: 'agents', label: 'Agents & X-Ray', icon: Cpu },
    { id: 'scenarios', label: 'Scenario Library', icon: Layers },
    { id: 'executions', label: 'Execution Sandbox', icon: Radio },
    { id: 'evaluations', label: 'Evaluation Engine', icon: Zap },
    { id: 'fix-agent', label: 'Fix My Agent', icon: Wrench },
    { id: 'live-attack', label: 'Live Attack', icon: Flame },
    { id: 'failures', label: 'Failure Clusters', icon: ShieldCheck },
    { id: 'scorecard', label: 'Regression Diff', icon: GitCompare },
    { id: 'calibration', label: 'Judge Calibration', icon: CheckCircle2 },
    { id: 'pipeline', label: 'Pipeline Monitor', icon: Radio },
  ];

  const handleMobileNav = (page: PageId) => {
    onNavigate(page);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-[#030712]/95 backdrop-blur-2xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div
            onClick={() => handleMobileNav('dashboard')}
            className="flex items-center space-x-3 cursor-pointer group select-none"
          >
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 via-indigo-500 to-rose-500 p-0.5 shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-300">
              <div className="w-full h-full bg-slate-950 rounded-[10px] flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-sm tracking-tight text-slate-100 font-mono">
                  AGY<span className="text-cyan-400">.RELIABILITY</span>
                </span>
                <span className="px-1.5 py-0.5 text-[9px] font-mono uppercase rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
                  v2.0 CI
                </span>
              </div>
              <p className="text-[10px] text-slate-400 -mt-0.5">Agent Reliability & Testing Engine</p>
            </div>
          </div>

          {/* Desktop Navigation Items */}
          <nav className="hidden xl:flex items-center space-x-1">
            {navItems.slice(0, 8).map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onNavigate(item.id)}
                  className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition-all duration-200 ${
                    isActive
                      ? 'bg-cyan-950/60 text-cyan-300 border border-cyan-500/40 shadow-sm shadow-cyan-500/20'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-900/60'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-500'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Status Badge & Mobile Hamburger Button */}
          <div className="flex items-center space-x-3">
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-[11px] font-mono">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>SANDBOX HEALTHY</span>
            </div>

            {/* Mobile Hamburger Toggle Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-xl bg-slate-900 border border-slate-700/80 text-slate-300 hover:text-white hover:bg-slate-800 transition focus:outline-none"
              aria-label="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5 text-rose-400" /> : <Menu className="w-5 h-5 text-cyan-400" />}
            </button>
          </div>
        </div>

        {/* Horizontal Fast-Bar for Tablets/Desktops */}
        <div className="hidden md:flex xl:hidden overflow-x-auto space-x-1 py-2 border-t border-slate-900 custom-scrollbar">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-medium whitespace-nowrap flex items-center space-x-1 transition ${
                  isActive
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Mobile Full Dropdown Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="absolute top-full left-0 right-0 py-3 px-4 border-b border-slate-800/90 bg-[#030712]/95 backdrop-blur-2xl shadow-xl shadow-black/50 space-y-1 animate-in slide-in-from-top duration-200">
            <div className="px-1 py-1 flex items-center justify-between text-[10px] font-mono text-slate-400 uppercase tracking-wider mb-1">
              <span>Platform Navigation</span>
              <span className="text-[9px] text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-500/30">13 Modules</span>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 max-h-[70vh] overflow-y-auto custom-scrollbar pr-1 pb-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = activePage === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleMobileNav(item.id)}
                    className={`w-full p-2 rounded-lg text-[11px] font-semibold flex items-center justify-between transition-all duration-200 ${
                      isActive
                        ? 'bg-cyan-950/80 text-cyan-300 border border-cyan-500/50 shadow-sm shadow-cyan-500/10'
                        : 'bg-slate-900/40 text-slate-300 border border-slate-800/60 hover:border-slate-700 hover:bg-slate-900'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <div className={`p-1 rounded-md ${isActive ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-400'}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-left">{item.label}</span>
                    </div>
                    <ChevronRight className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-600'}`} />
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </header>
  );
};
