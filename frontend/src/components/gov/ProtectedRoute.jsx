import React, { useState } from 'react';

/**
 * ProtectedRoute — DEMO-ONLY AUTH GATE
 * 
 * This is a simple passphrase gate for the Government Dashboard prototype.
 * It is NOT production-ready access control. No RBAC, no audit logging,
 * no session management. Replace with real authentication before deployment.
 * 
 * Default passphrase: "mospi2026" (can be overridden via VITE_GOV_PASSPHRASE env var)
 */

const DEMO_PASSPHRASE = import.meta.env.VITE_GOV_PASSPHRASE || 'mospi2026';

const ProtectedRoute = ({ children }) => {
  const [authenticated, setAuthenticated] = useState(false);
  const [input, setInput] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input === DEMO_PASSPHRASE) {
      setAuthenticated(true);
      setError('');
    } else {
      setError('Invalid access code. Please try again.');
    }
  };

  // DEMO-ONLY: Quick bypass for development
  const handleDemoAccess = () => {
    setAuthenticated(true);
  };

  if (authenticated) {
    return children;
  }

  return (
    <div className="max-w-lg mx-auto px-6 py-24 animate-fade-in">
      <div className="bg-white border border-border p-8 shadow-sm">
        {/* Header */}
        <div className="border-b border-border pb-6 mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 bg-navy rounded-sm flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>
            <div>
              <h2 className="font-serif text-2xl text-navy">Government Portal</h2>
              <p className="font-sans text-xs text-textSecondary">MoSPI / DGCA Restricted Access</p>
            </div>
          </div>
        </div>

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block font-sans text-xs text-textSecondary uppercase tracking-wider mb-2">
              Access Code
            </label>
            <input
              type="password"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter government access code"
              className="w-full border border-border bg-bg px-4 py-3 font-mono text-sm focus:ring-2 focus:ring-navy focus:border-navy outline-none transition-all"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-red text-xs font-sans">{error}</p>
          )}

          <button
            type="submit"
            className="w-full bg-navy text-white font-sans font-medium py-3 px-4 hover:bg-steel transition-colors text-sm tracking-wide"
          >
            Authenticate
          </button>
        </form>

        {/* Demo bypass — DEMO-ONLY, remove in production */}
        <div className="mt-6 pt-4 border-t border-border">
          <button
            onClick={handleDemoAccess}
            className="w-full text-center font-sans text-xs text-textSecondary hover:text-navy transition-colors py-2"
          >
            Demo Access (Skip Authentication) →
          </button>
          <p className="text-center font-sans text-[10px] text-textSecondary mt-2 italic">
            Demo-only auth gate — not for production use
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProtectedRoute;
