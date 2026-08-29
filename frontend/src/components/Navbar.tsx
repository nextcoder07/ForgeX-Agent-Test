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
  User as UserIcon,
  LogOut,
  ChevronDown,
  Trash2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

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
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const [sentNotice, setSentNotice] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, deleteAccount, sendVerificationEmail, reloadUser } = useAuth();

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

  const handleSignOut = async () => {
    setProfileDropdownOpen(false);
    await logout();
    navigate('/login');
  };

  const handleDeleteAccount = async () => {
    setProfileDropdownOpen(false);
    const confirmed = window.confirm(
      '⚠️ PERMANENT ACTION:\n\nAre you sure you want to delete your ForgeX account?\n\nThis will permanently delete your identity from Firebase Authentication AND delete all your workspaces, agents, scenarios, test executions, evaluation reports, and repairs from the Supabase database. This action cannot be undone.'
    );
    if (!confirmed) return;

    try {
      await deleteAccount();
      alert('Your account and all associated workspace data have been permanently deleted.');
      navigate('/signup');
    } catch (e: any) {
      alert(e.message || 'Failed to delete account.');
    }
  };

  const handleResend = async () => {
    await sendVerificationEmail();
    setSentNotice(true);
    setTimeout(() => setSentNotice(false), 5000);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-[#030712]/98 backdrop-blur-2xl">
      {user && user.emailVerified === false && (
        <div className="bg-gradient-to-r from-amber-500/15 via-indigo-500/15 to-cyan-500/15 border-b border-amber-500/30 px-4 py-1.5 text-xs text-amber-200 flex items-center justify-between">
          <span className="flex items-center gap-1.5 font-medium">
            <span>✉️</span> Please check your inbox and verify your email (<strong className="font-mono text-white">{user.email}</strong>).
          </span>
          <div className="flex items-center gap-2">
            {sentNotice ? (
              <span className="text-emerald-300 font-semibold">Link sent!</span>
            ) : (
              <button
                onClick={handleResend}
                className="underline hover:text-white font-semibold cursor-pointer"
              >
                Resend Link
              </button>
            )}
            <button
              onClick={() => reloadUser()}
              className="px-2 py-0.5 rounded bg-slate-900 border border-slate-700 hover:border-slate-500 text-slate-200 text-[10px] cursor-pointer"
            >
              I've Verified
            </button>
          </div>
        </div>
      )}
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <div
            onClick={() => navigate(user ? '/dashboard' : '/')}
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
              <p className="text-[9px] sm:text-[10px] text-slate-300 -mt-0.5">Agent Reliability & Security Testing</p>
            </div>
          </div>

          {/* Desktop Navigation Items */}
          {user && (
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
          )}

          {/* Right Side: User Profile / Auth State & Mobile Hamburger */}
          <div className="flex items-center space-x-2 sm:space-x-3">
            {user ? (
              <div className="relative">
                <button
                  onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
                  className="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-medium text-slate-200 transition-all cursor-pointer"
                >
                  {user.photoURL ? (
                    <img src={user.photoURL} alt="Avatar" className="w-5 h-5 rounded-full object-cover border border-cyan-500/40" />
                  ) : (
                    <div className="w-5 h-5 rounded-full bg-gradient-to-tr from-cyan-500 to-indigo-500 flex items-center justify-center text-[10px] font-bold text-slate-950 font-mono">
                      {user.displayName ? user.displayName.charAt(0).toUpperCase() : (user.email ? user.email.charAt(0).toUpperCase() : 'U')}
                    </div>
                  )}
                  <span className="hidden sm:inline max-w-[120px] truncate text-[11px] font-medium text-slate-300">
                    {user.displayName || user.email?.split('@')[0]}
                  </span>
                  <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
                </button>

                {profileDropdownOpen && (
                  <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-2 z-50 animate-fadeIn">
                    <div className="p-2.5 border-b border-slate-800/80 mb-1">
                      <p className="text-xs font-bold text-slate-100 truncate">{user.displayName || 'ForgeX User'}</p>
                      <p className="text-[10px] text-slate-400 font-mono truncate mt-0.5">{user.email}</p>
                    </div>
                    <button
                      onClick={handleSignOut}
                      className="w-full px-2.5 py-2 rounded-xl text-left text-xs font-semibold text-slate-300 hover:bg-slate-800 hover:text-white flex items-center gap-2 transition cursor-pointer"
                    >
                      <LogOut className="w-3.5 h-3.5 text-slate-400" />
                      <span>Sign Out</span>
                    </button>
                    <button
                      onClick={handleDeleteAccount}
                      className="w-full px-2.5 py-2 rounded-xl text-left text-xs font-semibold text-rose-400 hover:bg-rose-950/40 hover:text-rose-300 flex items-center gap-2 transition cursor-pointer mt-1 border-t border-slate-800/60 pt-2"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                      <span>Delete Account & Wipe Data</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => navigate('/login')}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-300 hover:text-white hover:bg-slate-900 transition cursor-pointer"
                >
                  Sign In
                </button>
                <button
                  onClick={() => navigate('/signup')}
                  className="px-3.5 py-1.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs shadow-sm transition cursor-pointer"
                >
                  Get Started
                </button>
              </div>
            )}

            {/* Mobile Hamburger Toggle Button */}
            {user && (
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="xl:hidden p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-200 hover:text-white opacity-100 cursor-pointer"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && user && (
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
