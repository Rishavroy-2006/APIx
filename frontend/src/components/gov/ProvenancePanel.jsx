import React, { useState, useEffect } from 'react';
import { getProvenanceStats } from '../../api/govClient.js';

/**
 * ProvenancePanel — Government Dashboard Component #2
 *
 * Compact stats strip showing data provenance for government audit trust:
 *   - Total quotes audited today
 *   - Overall scrape success rate
 *   - Per-route sample size breakdown
 *
 * Data source: getProvenanceStats() from govClient.js
 * Status: Derived from /api/fares/raw (REAL) when available,
 *         falls back to MOCK data if endpoint is unreachable.
 *         Indicator badge shows which source is active.
 */

const ProvenancePanel = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const data = await getProvenanceStats();
      setStats(data);
      setLoading(false);
    }
    load();
  }, []);

  if (loading || !stats) {
    return (
      <div className="bg-bg border border-border p-4 animate-pulse">
        <p className="font-sans text-sm text-textSecondary">Loading provenance data...</p>
      </div>
    );
  }

  return (
    <div className="bg-bg border border-border p-5 space-y-4">
      {/* Header Row */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <h3 className="font-serif text-lg text-navy">Data Provenance & Audit</h3>
          <span className={`text-[10px] font-sans font-medium uppercase tracking-wider px-2 py-0.5 rounded-sm border ${
            stats.source === 'live'
              ? 'bg-green/10 text-green border-green/20'
              : 'bg-saffron/10 text-saffron border-saffron/20'
          }`}>
            {stats.source === 'live' ? 'Live Data' : 'Mock Data'}
          </span>
        </div>

        {/* Aggregate KPIs */}
        <div className="flex gap-6 font-sans text-sm">
          <div className="flex items-baseline gap-2">
            <span className="text-textSecondary text-xs uppercase tracking-wider">Quotes Audited:</span>
            <span className="font-mono text-navy font-semibold">{stats.totalQuotes.toLocaleString()}</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-textSecondary text-xs uppercase tracking-wider">Success Rate:</span>
            <span className={`font-mono font-semibold ${
              stats.successRate >= 95 ? 'text-green' : stats.successRate >= 85 ? 'text-saffron' : 'text-red'
            }`}>
              {stats.successRate}%
            </span>
          </div>
        </div>
      </div>

      {/* Per-Route Breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {stats.routes.map(r => (
          <div key={r.route} className="bg-white border border-border p-3 flex flex-col items-center">
            <span className="font-sans text-xs font-semibold text-navy mb-1">{r.route}</span>
            <span className="font-mono text-lg text-textPrimary">{r.samples}</span>
            <span className="font-sans text-[10px] text-textSecondary">quotes</span>
            <div className="w-full bg-gray-200 h-1 mt-2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  r.successRate >= 95 ? 'bg-green' : r.successRate >= 85 ? 'bg-saffron' : 'bg-red'
                }`}
                style={{ width: `${r.successRate}%` }}
              />
            </div>
            <span className="font-mono text-[10px] text-textSecondary mt-1">{r.successRate}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProvenancePanel;
