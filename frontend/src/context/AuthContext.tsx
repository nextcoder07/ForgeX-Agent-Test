import React, { createContext, useContext, useEffect, useState } from 'react';
import {
  User,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  updateProfile
} from 'firebase/auth';
import { auth, googleProvider } from '../config/firebase';

export interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  signInWithEmail: (email: string, pass: string) => Promise<void>;
  signUpWithEmail: (email: string, pass: string, name?: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
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

    // Check localStorage for offline demo sessions first
    const savedUser = localStorage.getItem(LOCAL_STORAGE_USER_KEY);
    const savedToken = localStorage.getItem(LOCAL_STORAGE_TOKEN_KEY);
    if (savedUser && savedToken) {
      try {
        const parsed = JSON.parse(savedUser);
        setUser(parsed as any);
        setToken(savedToken);
      } catch (e) {
        localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
        localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
      }
    }

    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (!isMounted) return;
      if (firebaseUser) {
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
        } catch (err) {
          console.warn('Could not fetch Firebase ID token:', err);
        }
      } else {
        // If not in Firebase but in local storage session, keep local session
        if (!localStorage.getItem(LOCAL_STORAGE_USER_KEY)) {
          setUser(null);
          setToken(null);
        }
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
      const cred = await signInWithEmailAndPassword(auth, email, pass);
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
      // If Firebase key is demo/invalid, provide seamless local fallback
      if (firebaseErr.code?.includes('api-key') || firebaseErr.code?.includes('project') || firebaseErr.message?.includes('API key')) {
        const mockUid = `user-${Math.abs(hashString(email)).toString(16).slice(0, 10)}`;
        const mockToken = `token-simulated-${mockUid}`;
        const mockUserObj: any = {
          uid: mockUid,
          email: email,
          displayName: email.split('@')[0],
          getIdToken: async () => mockToken
        };
        setUser(mockUserObj);
        setToken(mockToken);
        localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify(mockUserObj));
        localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, mockToken);
        return;
      }
      throw firebaseErr;
    }
  };

  const signUpWithEmail = async (email: string, pass: string, name?: string) => {
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, pass);
      if (name && cred.user) {
        await updateProfile(cred.user, { displayName: name });
      }
      const idToken = await cred.user.getIdToken();
      setUser(cred.user);
      setToken(idToken);
      localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify({
        uid: cred.user.uid,
        email: cred.user.email,
        displayName: name || email.split('@')[0],
      }));
      localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, idToken);
    } catch (firebaseErr: any) {
      if (firebaseErr.code?.includes('api-key') || firebaseErr.code?.includes('project') || firebaseErr.message?.includes('API key')) {
        const mockUid = `user-${Math.abs(hashString(email)).toString(16).slice(0, 10)}`;
        const mockToken = `token-simulated-${mockUid}`;
        const mockUserObj: any = {
          uid: mockUid,
          email: email,
          displayName: name || email.split('@')[0],
          getIdToken: async () => mockToken
        };
        setUser(mockUserObj);
        setToken(mockToken);
        localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify(mockUserObj));
        localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, mockToken);
        return;
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
      if (firebaseErr.code?.includes('api-key') || firebaseErr.code?.includes('project') || firebaseErr.message?.includes('API key')) {
        const mockUid = `user-google-${Math.random().toString(16).slice(2, 10)}`;
        const mockToken = `token-simulated-${mockUid}`;
        const mockUserObj: any = {
          uid: mockUid,
          email: "google.user@example.com",
          displayName: "Google Demo User",
          getIdToken: async () => mockToken
        };
        setUser(mockUserObj);
        setToken(mockToken);
        localStorage.setItem(LOCAL_STORAGE_USER_KEY, JSON.stringify(mockUserObj));
        localStorage.setItem(LOCAL_STORAGE_TOKEN_KEY, mockToken);
        return;
      }
      throw firebaseErr;
    }
  };

  const logout = async () => {
    try {
      await signOut(auth);
    } catch (e) {
      // Ignore if signOut in mock mode
    } finally {
      setUser(null);
      setToken(null);
      localStorage.removeItem(LOCAL_STORAGE_USER_KEY);
      localStorage.removeItem(LOCAL_STORAGE_TOKEN_KEY);
      localStorage.removeItem('lastRegisteredAgent');
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        signInWithEmail,
        signUpWithEmail,
        signInWithGoogle,
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

function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const chr = str.charCodeAt(i);
    hash = (hash << 5) - hash + chr;
    hash |= 0;
  }
  return hash;
}
