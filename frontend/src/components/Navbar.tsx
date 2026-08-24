import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
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
  ChevronDown,
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

export const Navbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [moreDropdownOpen, setMoreDropdownOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Determine active page from current pathname
  const currentPath = location.pathname.split('/')[1] || 'dashboard';

  const navItems: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }>; category?: string }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'intake', label: '1. Agent Intake', icon: Sparkles },
    { id: 'scenarios', label: '2. Scenario Intel', icon: Layers },
    { id: 'dependencies', label: '3. Dep Gateway', icon: Layers },
    { id: 'executions', label: '4. Sandbox Run', icon: Radio },
    { id: 'evaluations', label: '5. Evaluation', icon: Zap },
    { id: 'fix-agent', label: '6. Fix My Agent', icon: Wrench },
    { id: 'agents', label: 'Agents X-Ray', icon: Cpu },
    { id: 'live-attack', label: 'Live Attack', icon: Flame },
    { id: 'failures', label: 'Failure Clusters', icon: ShieldCheck },
    { id: 'scorecard', label: 'Regression Diff', icon: GitCompare },
    { id: 'calibration', label: 'Judge Calibration', icon: CheckCircle2 },
    { id: 'pipeline', label: 'Pipeline Telemetry', icon: Radio },
  ];

  const handleNav = (page: PageId) => {
    navigate(`/${page}`);
  };

  const handleMobileNav = (page: PageId) => {
    handleNav(page);
    setMobileMenuOpen(false);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-[#030712]/98 backdrop-blur-2xl">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div
            onClick={() => handleMobileNav('dashboard')}
            className="flex items-center space-x-2.5 cursor-pointer group select-none"
          >
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-gradient-to-tr from-cyan-500 via-indigo-500 to-rose-500 p-0.5 shadow-md shadow-cyan-500/20 group-hover:scale-105 transition-transform duration-300">
              <div className="w-full h-full bg-slate-950 rounded-[7px] flex items-center justify-center">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
              </div>
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-extrabold text-xs sm:text-sm tracking-tight text-slate-100 font-mono">
                  <span className="text-cyan-400">FORGE</span>X
                </span>
                <span className="px-1 py-0.5 text-[8px] sm:text-[9px] font-mono uppercase rounded bg-cyan-500/15 text-cyan-300 border border-cyan-500/40">
                  v2.0 CI
                </span>
              </div>
              <p className="text-[9px] sm:text-[10px] text-slate-300 -mt-0.5">Agent Reliability, Evaluation & Self-Healing</p>
            </div>
          </div>

          {/* Desktop Navigation Items */}
          <nav className="hidden xl:flex items-center space-x-1">
            {navItems.slice(0, 7).map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNav(item.id)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center space-x-1 transition-all duration-200 ${
                    isActive
                      ? 'bg-cyan-950/80 text-cyan-200 border border-cyan-500/50 shadow-sm shadow-cyan-500/20 font-semibold'
                      : 'text-slate-300 hover:text-white hover:bg-slate-900/80'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}

            {/* Desktop More Modules Dropdown */}
            <div className="relative">
              <button
                onClick={() => setMoreDropdownOpen(!moreDropdownOpen)}
                className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center space-x-1 transition-all duration-200 ${
                  navItems.slice(7).some(i => i.id === currentPath)
                    ? 'bg-cyan-950/80 text-cyan-200 border border-cyan-500/50 font-semibold'
                    : 'text-slate-300 hover:text-white hover:bg-slate-900/80'
                }`}
              >
                <span>More ({navItems.length - 7})</span>
                <ChevronDown className="w-3.5 h-3.5 text-cyan-400" />
              </button>

              {moreDropdownOpen && (
                <div
                  onMouseLeave={() => setMoreDropdownOpen(false)}
                  className="absolute right-0 top-full mt-1.5 w-56 p-1.5 rounded-xl border border-slate-700 bg-[#030712]/98 backdrop-blur-2xl shadow-2xl shadow-black/80 space-y-1 z-50 animate-in fade-in duration-150"
                >
                  {navItems.slice(7).map((item) => {
                    const Icon = item.icon;
                    const isActive = currentPath === item.id;
                    return (
                      <button
                        key={item.id}
                        onClick={() => {
                          handleNav(item.id);
                          setMoreDropdownOpen(false);
                        }}
                        className={`w-full px-2.5 py-1.5 rounded-lg text-xs font-medium flex items-center justify-between transition ${
                          isActive
                            ? 'bg-cyan-950 text-cyan-200 border border-cyan-500/50 font-semibold'
                            : 'text-slate-300 hover:text-white hover:bg-slate-900/80'
                        }`}
                      >
                        <div className="flex items-center space-x-2">
                          <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                          <span>{item.label}</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          {/* Status Badge & Mobile Hamburger Button */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            <div className="hidden sm:flex items-center space-x-2 px-2.5 py-0.5 rounded-full bg-emerald-950/60 border border-emerald-500/40 text-emerald-300 text-[10px] font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>SANDBOX HEALTHY</span>
            </div>

            {/* Mobile Hamburger Toggle Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-1.5 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 hover:text-white hover:bg-slate-800 transition focus:outline-none"
              aria-label="Toggle Menu"
            >
              {mobileMenuOpen ? <X className="w-4 h-4 text-rose-400" /> : <Menu className="w-4 h-4 text-cyan-400" />}
            </button>
          </div>
        </div>

        {/* Horizontal Fast-Bar for Tablets/Desktops */}
        <div className="hidden md:flex xl:hidden overflow-x-auto space-x-1 py-1.5 border-t border-slate-800 custom-scrollbar">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium whitespace-nowrap flex items-center space-x-1 transition ${
                  isActive
                    ? 'bg-cyan-950 text-cyan-200 border border-cyan-500/50'
                    : 'text-slate-300 hover:text-white hover:bg-slate-900/60'
                }`}
              >
                <Icon className="w-3.5 h-3.5 text-cyan-400" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>

        {/* Mobile Full Dropdown Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="absolute top-full left-0 right-0 py-2.5 px-3 border-b border-slate-800 bg-[#030712]/98 backdrop-blur-2xl shadow-2xl shadow-black/80 space-y-1 animate-in slide-in-from-top duration-200">
            <div className="px-1 py-0.5 flex items-center justify-between text-[10px] font-mono text-slate-300 uppercase tracking-wider mb-1">
              <span>Platform Navigation</span>
              <span className="text-[9px] text-cyan-300 bg-cyan-950/80 px-1.5 py-0.5 rounded border border-cyan-500/40">13 Modules</span>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-[70vh] overflow-y-auto custom-scrollbar pr-1 pb-2">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = currentPath === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleMobileNav(item.id)}
                    className={`w-full p-2 rounded-lg text-[11px] font-medium flex items-center justify-between transition-all duration-200 ${
                      isActive
                        ? 'bg-cyan-950 text-cyan-200 border border-cyan-500/60 shadow-sm shadow-cyan-500/10 font-semibold'
                        : 'bg-slate-900/60 text-slate-200 border border-slate-800 hover:border-slate-700 hover:bg-slate-800/80'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <div className={`p-1 rounded-md ${isActive ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-300'}`}>
                        <Icon className="w-3.5 h-3.5" />
                      </div>
                      <span className="text-left">{item.label}</span>
                    </div>
                    <ChevronRight className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
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
