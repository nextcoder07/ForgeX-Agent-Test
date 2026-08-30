import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Menu, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface TopHeaderProps {
  onToggleMobileMenu?: () => void;
}

export const TopHeader: React.FC<TopHeaderProps> = ({ onToggleMobileMenu }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const pathParts = location.pathname.split('/').filter(Boolean);
  const pageTitle = pathParts[0] ? pathParts[0].charAt(0).toUpperCase() + pathParts[0].slice(1) : 'Dashboard';

  return (
    <header className="h-14 border-b border-slate-800/80 bg-[#020617]/90 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 font-mono text-xs">
      
      {/* Left: Mobile Toggle & Page Greeting / Breadcrumb */}
      <div className="flex items-center space-x-3">
        {onToggleMobileMenu && (
          <button
            onClick={onToggleMobileMenu}
            className="md:hidden p-1.5 rounded-lg border border-slate-800 bg-slate-900 text-slate-300 hover:text-white cursor-pointer"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}

        <div>
          <h1 className="text-sm font-extrabold text-slate-100 flex items-center space-x-1.5">
            <span className="text-slate-400">Workspace /</span>
            <span className="text-cyan-400">{pageTitle}</span>
          </h1>
        </div>
      </div>

    </header>
  );
};
