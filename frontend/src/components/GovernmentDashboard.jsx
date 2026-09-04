import React from 'react';
import ProtectedRoute from './gov/ProtectedRoute.jsx';
import NationalTrendChart from './gov/NationalTrendChart.jsx';
import ProvenancePanel from './gov/ProvenancePanel.jsx';
import ContributionBreakdown from './gov/ContributionBreakdown.jsx';
import RouteHeatmap from './gov/RouteHeatmap.jsx';

/**
 * GovernmentDashboard — Main container for the MoSPI / DGCA Policy Portal
 *
 * Answers: "What is airfare inflation doing, and why?"
 *
 * Wrapped in ProtectedRoute (demo-only auth gate).
 * All data fetched through govClient.js (centralized API client).
 *
 * Components rendered in order:
 *   1. NationalTrendChart — Macro index trend with MoM/YoY toggle
 *   2. ProvenancePanel — Data audit strip (sample counts, success rates)
 *   3. ContributionBreakdown — Route contributions to index movement
 *   4. RouteHeatmap — Sortable sector table with VolatilitySignal badges
 */

const GovernmentDashboard = () => {
  return (
    <ProtectedRoute>
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 animate-fade-in">

        {/* Portal Header */}
        <div className="border-b border-border pb-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <span className="bg-navy text-white font-mono text-xs px-2 py-1 rounded-sm uppercase tracking-wider">
                  Gov Portal
                </span>
                <span className="bg-saffron/10 text-saffron font-sans text-xs px-2 py-1 rounded-sm border border-saffron/20 uppercase tracking-wider">
                  Prototype
                </span>
              </div>
              <h2 className="font-serif text-3xl text-navy">
                MoSPI Airfare Inflation Intelligence
              </h2>
              <p className="font-sans text-sm text-textSecondary mt-1">
                Real-time DGCA-weighted index, route-level decomposition, and data provenance audit
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs font-sans text-textSecondary">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Audit-logged session (demo mode)
            </div>
          </div>
        </div>

        {/* 1. National Trend */}
        <NationalTrendChart />

        {/* 2. Data Provenance */}
        <ProvenancePanel />

        {/* 3. Route Contribution */}
        <ContributionBreakdown />

        {/* 4. Route Heatmap + Volatility Signals */}
        <RouteHeatmap />

        {/* Footer Note */}
        <div className="text-xs font-sans text-textSecondary border-t border-border pt-4 flex flex-col md:flex-row justify-between gap-2">
          <span>
            Udaan Metrics Government Portal &middot; SIH Problem Statement 26056 &middot; Submitted to MoSPI
          </span>
          <span className="italic">
            Data refreshed daily via automated scraping pipeline &middot; Weights pending official DGCA traffic report
          </span>
        </div>

      </div>
    </ProtectedRoute>
  );
};

export default GovernmentDashboard;
