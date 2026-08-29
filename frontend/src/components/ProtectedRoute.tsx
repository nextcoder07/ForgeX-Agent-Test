import React, { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Cpu, Mail, AlertCircle, RefreshCw, LogOut } from 'lucide-react';

export const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, loading, emailVerified, reloadUser, sendVerificationEmail, logout } = useAuth();
  const location = useLocation();
  const [checking, setChecking] = useState(false);
  const [resendStatus, setResendStatus] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [timedOut, setTimedOut] = useState(false);

  React.useEffect(() => {
    if (loading) {
      const t = setTimeout(() => setTimedOut(true), 800);
      return () => clearTimeout(t);
    }
  }, [loading]);

  if (loading && !timedOut && !user) {
    return (
      <div className="min-h-screen bg-[#030712] flex flex-col items-center justify-center space-y-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-cyan-500 to-indigo-500 animate-pulse flex items-center justify-center shadow-lg shadow-cyan-500/20">
            <Cpu className="w-6 h-6 text-white animate-spin" />
          </div>
        </div>
        <p className="text-xs font-mono text-slate-400">Authenticating ForgeX workspace session...</p>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Strict email verification enforcement
  const isGoogle = user.providerData?.some(p => p.providerId === 'google.com');
  const isVerified = isGoogle || emailVerified || user.emailVerified;

  if (!isVerified) {
    const handleCheckVerification = async () => {
      setChecking(true);
      setErrorMsg('');
      try {
        const verified = await reloadUser();
        if (!verified) {
          setErrorMsg('Email is still unverified. Please open your inbox, click the confirmation link, and check again.');
        }
      } catch (err: any) {
        setErrorMsg('Error checking verification status.');
      } finally {
        setChecking(false);
      }
    };

    const handleResend = async () => {
      setResendStatus('Sending verification email...');
      setErrorMsg('');
      try {
        await sendVerificationEmail();
        setResendStatus('Verification link sent! Check your inbox & spam.');
        setTimeout(() => setResendStatus(''), 5000);
      } catch (e: any) {
        setResendStatus('Failed to send verification email. Try again later.');
      }
    };

    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center p-4 relative">
        <div className="w-full max-w-md bg-slate-900/90 border border-amber-500/30 rounded-2xl p-8 backdrop-blur-xl shadow-2xl text-center space-y-6 animate-fadeIn">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-amber-500/20 to-orange-500/20 border border-amber-500/40 flex items-center justify-center mx-auto text-amber-400 shadow-lg shadow-amber-500/10">
            <Mail className="w-7 h-7" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-bold text-slate-100">Email Confirmation Required</h2>
            <p className="text-xs text-slate-300 leading-relaxed">
              We need to confirm you own <span className="font-mono text-cyan-400 font-semibold">{user.email}</span> before granting workspace access.
            </p>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs flex items-start gap-2 text-left">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">{errorMsg}</div>
            </div>
          )}

          {resendStatus && (
            <div className="p-2.5 rounded-xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 text-xs">
              {resendStatus}
            </div>
          )}

          <div className="space-y-3 pt-2">
            <button
              onClick={handleCheckVerification}
              disabled={checking}
              className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-slate-950 font-bold text-xs shadow-md shadow-cyan-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <RefreshCw className={`w-4 h-4 ${checking ? 'animate-spin' : ''}`} />
              <span>{checking ? 'Checking Status...' : "I've Clicked the Verification Link"}</span>
            </button>

            <button
              onClick={handleResend}
              className="w-full py-2.5 rounded-xl bg-slate-950/80 hover:bg-slate-800 border border-slate-800 text-slate-300 font-semibold text-xs transition cursor-pointer"
            >
              Resend Verification Email
            </button>

            <button
              onClick={logout}
              className="w-full py-2 rounded-xl text-slate-400 hover:text-slate-200 text-xs font-semibold flex items-center justify-center gap-1.5 transition cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out & Use Different Account</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};
