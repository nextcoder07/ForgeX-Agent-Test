import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, CheckCircle2, AlertCircle, RefreshCw, LogOut, Cpu, ArrowRight } from 'lucide-react';

export const VerifyEmailPage: React.FC = () => {
  const { user, reloadUser, sendVerificationEmail, logout } = useAuth();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);
  const [resendStatus, setResendStatus] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const email = user?.email || 'your email';

  const handleCheckVerification = async () => {
    setChecking(true);
    setErrorMsg('');
    try {
      const verified = await reloadUser();
      if (verified) {
        navigate('/agents', { replace: true });
      } else {
        setErrorMsg('Your email is not verified yet. Please open the confirmation email, click the verification link, and click below again.');
      }
    } catch (err: any) {
      setErrorMsg('Could not verify status. Please ensure you have clicked the link in your email.');
    } finally {
      setChecking(false);
    }
  };

  const handleResend = async () => {
    setResendStatus('Sending verification link...');
    setErrorMsg('');
    try {
      await sendVerificationEmail();
      setResendStatus('A fresh verification link has been sent to ' + email);
      setTimeout(() => setResendStatus(''), 5000);
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to resend verification email. Please wait a moment.');
    }
  };

  return (
    <div className="min-h-screen bg-[#030712] flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background glow */}
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-gradient-to-tr from-cyan-600/10 via-indigo-600/15 to-purple-600/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-3 z-10">
        <Link to="/" className="inline-flex items-center gap-2.5 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition-transform">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <span className="text-2xl font-black tracking-tight text-white font-mono">FORGE<span className="text-cyan-400">X</span></span>
        </Link>
        <h2 className="text-xl font-extrabold text-slate-100">Email Verification Required</h2>
        <p className="text-xs text-slate-400">
          Verify email ownership before activating your ForgeX workspace
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10 px-4 sm:px-0">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl space-y-6 text-center animate-fadeIn">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400 shadow-lg shadow-cyan-500/10">
            <Mail className="w-8 h-8" />
          </div>

          <div className="space-y-2">
            <h3 className="text-lg font-bold text-slate-100">Check Your Email</h3>
            <p className="text-xs text-slate-300 leading-relaxed">
              We sent a verification link to <span className="font-mono text-cyan-300 font-semibold">{email}</span>.
            </p>
            <p className="text-[11px] text-slate-400">
              You must verify this email address before accessing ForgeX workspace resources.
            </p>
          </div>

          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-amber-950/60 border border-amber-500/40 text-amber-300 text-xs flex items-start gap-2.5 text-left animate-fadeIn">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div className="flex-1 leading-relaxed">{errorMsg}</div>
            </div>
          )}

          {resendStatus && (
            <div className="p-2.5 rounded-xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 text-xs animate-fadeIn">
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
              <span>{checking ? 'Checking Status...' : "I've Verified My Email → Enter Workspace"}</span>
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
              <span>Sign In with Different Account</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
