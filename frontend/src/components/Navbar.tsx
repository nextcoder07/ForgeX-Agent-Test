import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Activity,
  Layers,
  Sparkles,
  Zap,
  Server,
  Radio,
  Wrench,
  Cpu,
  ShieldCheck,
  Menu,
  X,
} from 'lucide-react';

export type PageId =
  | 'dashboard'
  | 'agents'
  | 'scenarios'
  | 'setup'
  | 'executions'
  | 'results'
  | 'improve'
  | 'platform-ai';

export const Navbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  // Determine active page from current pathname
  const currentPath = location.pathname.split('/')[1] || 'dashboard';

  const navItems: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: Activity },
    { id: 'agents', label: '1. Agents', icon: Sparkles },
    { id: 'scenarios', label: '2. Scenarios', icon: Layers },
    { id: 'setup', label: '3. Setup', icon: Server },
    { id: 'executions', label: '4. Execute', icon: Radio },
    { id: 'results', label: '5. Results', icon: Zap },
    { id: 'improve', label: '6. Improve', icon: Wrench },
    { id: 'platform-ai', label: 'ForgeX AI Lab', icon: Cpu },
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
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = currentPath === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleNav(item.id)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold flex items-center space-x-1 transition-all duration-200 cursor-pointer ${
                    isActive
                      ? 'bg-cyan-950 text-cyan-200 border border-cyan-500/50 shadow-sm shadow-cyan-500/20'
                      : 'text-slate-300 hover:text-white hover:bg-slate-900/80'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
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
              className="xl:hidden p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-200 hover:text-white opacity-100 cursor-pointer"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="xl:hidden border-t border-slate-800 bg-[#030712]/98 backdrop-blur-2xl p-4 space-y-2 animate-in slide-in-from-top-4 duration-200">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleMobileNav(item.id)}
                className={`w-full px-3 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2.5 transition cursor-pointer ${
                  isActive
                    ? 'bg-cyan-950 text-cyan-200 border border-cyan-500/50 shadow-sm shadow-cyan-500/20'
                    : 'text-slate-300 hover:text-white hover:bg-slate-900/80'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
};
