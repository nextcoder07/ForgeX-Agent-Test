import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  Cpu,
  Lock,
  Mail,
  User as UserIcon,
  ArrowRight,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  ShieldCheck
} from 'lucide-react';

export const SignupPage: React.FC = () => {
  const navigate = useNavigate();
  const { signUpWithEmail, signInWithGoogle, sendVerificationEmail, reloadUser, user } = useAuth();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [verificationSent, setVerificationSent] = useState(false);
  const [resendStatus, setResendStatus] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError('Please fill in all required fields.');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match. Please verify your password.');
      return;
    }

    setError('');
    setLoading(true);
    try {
      await signUpWithEmail(email.trim(), password, name.trim());
      setVerificationSent(true);
    } catch (err: any) {
      console.error('Sign up error:', err);
      if (err.code === 'auth/email-already-in-use') {
        setError('An account with this email already exists. Try signing in instead.');
      } else if (err.code === 'auth/weak-password') {
        setError('The password is too weak. Please use a stronger combination.');
      } else {
        setError(err.message || 'Failed to create account. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const [verificationError, setVerificationError] = useState('');

  const handleResendVerification = async () => {
    setResendStatus('Sending...');
    setVerificationError('');
    try {
      await sendVerificationEmail();
      setResendStatus('Verification link resent to your email!');
      setTimeout(() => setResendStatus(''), 4000);
    } catch (err: any) {
      setResendStatus('Could not resend link. Please try again in a few moments.');
    }
  };

  const handleContinue = async () => {
    setVerificationError('');
    setLoading(true);
    try {
      const isVerified = await reloadUser();
      if (isVerified) {
        navigate('/agents', { replace: true });
      } else {
        setVerificationError(`Email not verified yet. Please check your inbox (and spam folder) for the verification link sent to ${email}, click it, and try again.`);
      }
    } catch (err: any) {
      setVerificationError('Could not verify status. Please make sure you have clicked the link in your email.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setError('');
    setLoading(true);
    try {
      await signInWithGoogle();
      navigate('/agents', { replace: true });
    } catch (err: any) {
      console.error('Google sign up error:', err);
      setError(err.message || 'Failed to authenticate with Google.');
    } finally {
      setLoading(false);
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
        <h2 className="text-xl font-extrabold text-slate-100">Create your workspace account</h2>
        <p className="text-xs text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-cyan-400 hover:text-cyan-300 transition-colors">
            Sign in
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md z-10 px-4 sm:px-0">
        <div className="bg-slate-900/80 border border-slate-800/80 rounded-2xl p-6 sm:p-8 backdrop-blur-xl shadow-2xl space-y-6">
          {verificationSent ? (
            <div className="text-center space-y-5 animate-fadeIn">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 flex items-center justify-center mx-auto text-cyan-400 shadow-lg shadow-cyan-500/10">
                <Mail className="w-7 h-7" />
              </div>
              <div className="space-y-1.5">
                <h3 className="text-lg font-bold text-slate-100">Verify Your Email Address</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  We've sent a verification link to <span className="font-mono text-cyan-300 font-semibold">{email}</span>.
                </p>
                <p className="text-[11px] text-slate-400">
                  Please click the link in your email to activate your account.
                </p>
              </div>

              {verificationError && (
                <div className="p-3.5 rounded-xl bg-amber-950/60 border border-amber-500/50 text-amber-300 text-xs flex items-start gap-2.5 text-left animate-fadeIn">
                  <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                  <div className="flex-1 leading-relaxed">{verificationError}</div>
                </div>
              )}

              {resendStatus && (
                <div className="p-2.5 rounded-xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-300 text-xs">
                  {resendStatus}
                </div>
              )}

              <div className="space-y-2.5 pt-2">
                <button
                  type="button"
                  onClick={handleContinue}
                  disabled={loading}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 text-slate-950 font-bold text-xs shadow-md shadow-cyan-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>{loading ? 'Checking Verification...' : "I've Verified My Email → Enter Workspace"}</span>
                </button>

                <button
                  type="button"
                  onClick={handleResendVerification}
                  className="w-full py-2.5 rounded-xl bg-slate-950/80 hover:bg-slate-800 border border-slate-800 text-slate-300 font-semibold text-xs transition cursor-pointer"
                >
                  Resend Verification Email
                </button>
              </div>
            </div>
          ) : (
            <>
              {error && (
                <div className="p-3.5 rounded-xl bg-rose-950/50 border border-rose-500/40 text-rose-300 text-xs flex items-start gap-2.5 animate-fadeIn">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                  <div className="flex-1 leading-relaxed">{error}</div>
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Full Name</label>
                  <div className="relative">
                    <UserIcon className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Alex Mercer"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/80 text-xs text-slate-100 placeholder-slate-500 transition-all outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Email Address *</label>
                  <div className="relative">
                    <Mail className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@company.com"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/80 text-xs text-slate-100 placeholder-slate-500 transition-all outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Password (min 6 characters) *</label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/80 text-xs text-slate-100 placeholder-slate-500 transition-all outline-none"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300">Confirm Password *</label>
                  <div className="relative">
                    <Lock className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                    <input
                      type="password"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••••••"
                      className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-950/60 border border-slate-800 focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/80 text-xs text-slate-100 placeholder-slate-500 transition-all outline-none"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold text-xs shadow-md shadow-cyan-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 mt-2"
                >
                  {loading ? (
                    <span>Creating workspace...</span>
                  ) : (
                    <>
                      <span>Create Account</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              </form>

              <div className="relative flex items-center justify-center">
                <div className="border-t border-slate-800 w-full" />
                <span className="bg-slate-900 px-3 text-[11px] font-mono text-slate-500 uppercase tracking-wider absolute">
                  or
                </span>
              </div>

              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={loading}
                className="w-full py-2.5 rounded-xl bg-slate-950/80 hover:bg-slate-800/80 border border-slate-800 text-slate-200 font-semibold text-xs transition-all flex items-center justify-center gap-2.5 cursor-pointer disabled:opacity-50"
              >
                <svg className="w-4 h-4" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.34 24 12 24z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 10.03 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                  />
                </svg>
                <span>Sign up with Google</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
