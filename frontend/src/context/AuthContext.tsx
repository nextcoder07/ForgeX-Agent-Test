import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  deleteUser,
  onAuthStateChanged,
  updateProfile,
  sendEmailVerification
} from 'firebase/auth';
import { auth, googleProvider } from '../config/firebase';
import { API_BASE_URL } from '../api/client';

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
  deleteAccount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const LOCAL_STORAGE_USER_KEY = 'forgex_active_user_session';
const LOCAL_STORAGE_TOKEN_KEY = 'forgex_active_user_token';

// Server-side profile & workspace bootstrap synchronizer with timeout protection
const syncProfileToBackend = async (firebaseUser: User, idToken: string) => {
  try {
    const url = `${API_BASE_URL}/auth/bootstrap`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 2500); // 2.5s max timeout

    const res = await fetch(url, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${idToken}`,
        'X-User-ID': firebaseUser.uid,
        'X-User-Email': firebaseUser.email || '',
        'X-User-Email-Verified': 'true'
      },
      body: JSON.stringify({
        display_name: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
        avatar_url: firebaseUser.photoURL || undefined
      })
    });
    clearTimeout(timer);

    if (res.ok) {
      const data = await res.json();
      if (data?.active_workspace?.id) {
        localStorage.setItem('forgex_active_workspace_id', data.active_workspace.id);
        localStorage.setItem('forgex_active_workspace', JSON.stringify(data.active_workspace));
      }
    }
  } catch (err) {
    // Non-blocking background sync warning
    console.debug('Background profile sync note:', err);
  }
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => auth.currentUser);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(LOCAL_STORAGE_TOKEN_KEY));
  const [loading, setLoading] = useState<boolean>(!auth.currentUser && !localStorage.getItem(LOCAL_STORAGE_USER_KEY));

  // Synchronize Firebase Auth state
  useEffect(() => {
    let isMounted = true;

    // Safety timeout: Never keep loading spinner stuck for more than 1 second
    const fallbackTimer = setTimeout(() => {
      if (isMounted) setLoading(false);
    }, 1000);

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      clearTimeout(fallbackTimer);
      if (!isMounted) return;

      if (firebaseUser) {
        const isGoogle = firebaseUser.providerData.some(p => p.providerId === 'google.com');
        const isVerified = isGoogle || firebaseUser.emailVerified;

        if (isVerified) {
          try {
            setUser(firebaseUser);
            setLoading(false); // Unblock UI immediately!

            const idToken = await firebaseUser.getIdToken();
            if (!isMounted) return;

            setToken(idToken);
            localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
              uid: firebaseUser.uid,
              email: firebaseUser.email,
              displayName: firebaseUser.displayName || firebaseUser.email?.split('@')[0] || 'User',
              photoURL: firebaseUser.photoURL
            }));
            localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);

            // Sync user profile & workspace into Supabase in background without blocking UI
            syncProfileToBackend(firebaseUser, idToken);
            return;
          } catch (err) {
            console.warn('Could not fetch Firebase ID token:', err);
          }
        } else {
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
      if (isMounted) {
        setLoading(false);
      }
    });

    return () => {
      isMounted = false;
      clearTimeout(fallbackTimer);
      unsubscribe();
    };
  }, []);

  const signInWithEmail = async (email: string, pass: string) => {
    try {
      const cred = await signInWithEmailAndPassword(auth, email.trim(), pass);
      
      // Strict verification check
      if (!cred.user.emailVerified) {
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

      // Await server sync to guarantee Supabase record exists before navigating
      await syncProfileToBackend(cred.user, idToken);
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

      // Await server sync to guarantee Supabase record exists before navigating
      await syncProfileToBackend(cred.user, idToken);
    } catch (firebaseErr: any) {
      console.error('Firebase Google auth error:', firebaseErr.code, firebaseErr.message);
      if (firebaseErr.code === 'auth/popup-closed-by-user') {
        throw new Error('Google sign-in window was closed before completion.');
      } else if (firebaseErr.code === 'auth/popup-blocked') {
        throw new Error('Google popup was blocked by browser. Please allow popups for localhost.');
      } else if (firebaseErr.code === 'auth/account-exists-with-different-credential') {
        throw new Error('An account already exists with this email address. Please sign in with email and password.');
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

        // Sync verified user profile & default workspace into Supabase backend
        await syncProfileToBackend(updated, idToken);

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

  const deleteAccount = async (): Promise<void> => {
    const currentUser = auth.currentUser;
    const currentToken = token || (currentUser ? await currentUser.getIdToken() : null);

    // 1. Delete all Supabase workspaces, agents, runs, and user profile in backend
    try {
      if (currentToken) {
        await fetch(`${API_BASE_URL}/auth/me`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${currentToken}`,
            'X-User-ID': currentUser?.uid || ''
          }
        });
      }
    } catch (err) {
      console.warn('Backend data deletion note:', err);
    }

    // 2. Delete user from Firebase Authentication
    if (currentUser) {
      try {
        await deleteUser(currentUser);
      } catch (fbErr: any) {
        console.error('Firebase deleteUser error:', fbErr);
        if (fbErr.code === 'auth/requires-recent-login') {
          throw new Error('For security, deleting your account requires a recent login. Please sign in again and retry.');
        }
        throw fbErr;
      }
    }

    // 3. Purge all local state
    setUser(null);
    setToken(null);
    localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
    localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
    localStorage.removeItem('forgex_active_workspace_id');
    localStorage.removeItem('forgex_active_workspace');
    localStorage.removeItem('lastRegisteredAgent');
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
        logout,
        deleteAccount
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
