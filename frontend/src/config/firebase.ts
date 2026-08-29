import { initializeApp, getApps, getApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';

// Firebase configuration from Vite environment variables with fallback defaults
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || "AIzaSyDemoDummyKeyForForgeXSandboxApp9812",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || "forgex-platform.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || "forgex-platform",
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || "forgex-test-agent.firebasestorage.app",
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || "797590506413",
  appId: import.meta.env.VITE_FIREBASE_APP_ID || "1:797590506413:web:dfc95c75d6c46a00d82f24",
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || "G-CLN40KHN75",
};

// Initialize Firebase App singleton safely
export const app = getApps().length > 0 ? getApp() : initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({
  prompt: 'select_account'
});
