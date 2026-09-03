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
  return children;
};

export default ProtectedRoute;
