import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  updateProfile,
  sendEmailVerification
} from 'firebase/auth';
import { auth, googleProvider } from '../config/firebase';

export interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  emailVerified: boolean;
  signInWithEmail: (email: string, pass: string) => Promise<void>;
  signUpWithEmail: (email: string, pass: string, name?: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  sendVerificationEmail: () => Promise<void>;
  reloadUser: () => Promise<boolean>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const LOCAL_STORAGE_USER_KEY = 'forgex_active_user_session';
const LOCAL_STORAGE_TOKEN_KEY = 'forgex_active_user_token';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Synchronize Firebase Auth state
  useEffect(() => {
    let isMounted = true;

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (!isMounted) return;
      if (firebaseUser) {
        // Enforce email verification strictly for non-OAuth password logins
        const isGoogle = firebaseUser.providerData.some(p => p.providerId === 'google.com');
        const isVerified = isGoogle || firebaseUser.emailVerified;

        if (isVerified) {
          try {
            const idToken = await firebaseUser.getIdToken();
            setUser(firebaseUser);
            setToken(idToken);
            localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
              uid: firebaseUser.uid,
              email: firebaseUser.email,
              displayName: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
              photoURL: firebaseUser.photoURL
            }));
            localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);

            // Background bootstrap user profile and default workspace in backend
            fetch('/api/auth/bootstrap', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ display_name: firebaseUser.displayName || undefined })
            }).then(res => res.ok ? res.json() : null).then(data => {
              if (data?.active_workspace?.id) {
                localStorage.setItem('forgex_active_workspace_id', data.active_workspace.id);
                localStorage.setItem('forgex_active_workspace', JSON.stringify(data.active_workspace));
              }
            }).catch(() => {});
          } catch (err) {
            console.warn('Could not fetch Firebase ID token:', err);
          }
        } else {
          // Unverified user is not granted active authenticated token
          setUser(firebaseUser);
          setToken(null);
          localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
        }
      } else {
        setUser(null);
        setToken(null);
        localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
        localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  const signInWithEmail = async (email: string, pass: string) => {
    try {
      const cred = await signInWithEmailAndPassword(auth, email.trim(), pass);
      
      // Strict verification check
      if (!cred.user.emailVerified) {
        // Send a fresh verification email just in case
        try {
          await sendEmailVerification(cred.user);
        } catch (e) {}
        await signOut(auth);
        setUser(null);
        setToken(null);
        localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
        localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
        throw new Error('Your email address has not been verified yet. We have sent a verification link to your email. Please verify it before signing in.');
      }

      const idToken = await cred.user.getIdToken();
      setUser(cred.user);
      setToken(idToken);
      localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
        uid: cred.user.uid,
        email: cred.user.email,
        displayName: cred.user.displayName || email.split('@')[0],
      }));
      localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);
    } catch (firebaseErr: any) {
      console.error('Firebase sign-in error:', firebaseErr.code, firebaseErr.message);
      if (firebaseErr.code === 'auth/invalid-credential' || firebaseErr.code === 'auth/wrong-password' || firebaseErr.code === 'auth/user-not-found') {
        throw new Error('Invalid email or password. Please verify your credentials.');
      } else if (firebaseErr.code === 'auth/too-many-requests') {
        throw new Error('Too many unsuccessful attempts. Please try again in a few minutes.');
      } else if (firebaseErr.code === 'auth/network-request-failed') {
        throw new Error('Network connection failed. Please check your internet connection or pause ad-blockers.');
      }
      throw firebaseErr;
    }
  };

  const signUpWithEmail = async (email: string, pass: string, name?: string) => {
    try {
      const cred = await createUserWithEmailAndPassword(auth, email.trim(), pass);
      if (name && cred.user) {
        await updateProfile(cred.user, { displayName: name.trim() });
      }
      // Send real email verification
      await sendEmailVerification(cred.user);
      
      // Keep user in context for verification screen, but do NOT give active token yet
      setUser(cred.user);
      setToken(null);
      localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
    } catch (firebaseErr: any) {
      console.error('Firebase signup error:', firebaseErr.code, firebaseErr.message);
      if (firebaseErr.code === 'auth/email-already-in-use') {
        throw new Error('An account with this email already exists. Try signing in instead.');
      } else if (firebaseErr.code === 'auth/weak-password') {
        throw new Error('Password is too weak. Please use at least 6 characters.');
      } else if (firebaseErr.code === 'auth/network-request-failed') {
        throw new Error('Network connection to Firebase failed. Check your internet connection or pause browser extensions/ad-blockers.');
      }
      throw firebaseErr;
    }
  };

  const signInWithGoogle = async () => {
    try {
      const cred = await signInWithPopup(auth, googleProvider);
      const idToken = await cred.user.getIdToken();
      setUser(cred.user);
      setToken(idToken);
      localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
        uid: cred.user.uid,
        email: cred.user.email,
        displayName: cred.user.displayName || cred.user.email?.split('@')[0] || 'Google User',
        photoURL: cred.user.photoURL
      }));
      localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);
    } catch (firebaseErr: any) {
      console.error('Firebase Google auth error:', firebaseErr.code, firebaseErr.message);
      if (firebaseErr.code === 'auth/popup-closed-by-user') {
        throw new Error('Google sign-in window was closed before completion.');
      } else if (firebaseErr.code === 'auth/popup-blocked') {
        throw new Error('Google popup was blocked by browser. Please allow popups for localhost.');
      } else if (firebaseErr.code === 'auth/operation-not-allowed') {
        throw new Error('Google Sign-In is not enabled in Firebase Console. Enable Google provider in Authentication > Sign-in method.');
      } else if (firebaseErr.code === 'auth/unauthorized-domain') {
        throw new Error(`Domain '${window.location.hostname}' is not authorized in Firebase Console.`);
      }
      throw new Error(firebaseErr.message || 'Failed to authenticate with Google.');
    }
  };

  const sendVerificationEmail = async () => {
    if (auth.currentUser) {
      try {
        await sendEmailVerification(auth.currentUser);
      } catch (err: any) {
        console.warn('Could not send verification email:', err);
        throw new Error(err.message || 'Failed to send verification email.');
      }
    }
  };

  const reloadUser = async (): Promise<boolean> => {
    if (auth.currentUser) {
      await auth.currentUser.reload();
      const updated = auth.currentUser;
      setUser(updated);
      if (updated.emailVerified) {
        const idToken = await updated.getIdToken(true);
        setToken(idToken);
        localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
          uid: updated.uid,
          email: updated.email,
          displayName: updated.displayName || updated.email?.split('@')[0] || 'User',
          photoURL: updated.photoURL
        }));
        localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);
        return true;
      }
    }
    return false;
  };

  const logout = async () => {
    try {
      await signOut(auth);
    } catch (e) {
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
      localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
      localStorage.removeItem('forgex_active_workspace_id');
      localStorage.removeItem('forgex_active_workspace');
      localStorage.removeItem('lastRegisteredAgent');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        emailVerified: user?.emailVerified ?? false,
        signInWithEmail,
        signUpWithEmail,
        signInWithGoogle,
        sendVerificationEmail,
        reloadUser,
        logout
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
