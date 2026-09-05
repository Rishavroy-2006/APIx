import React, { useState, useEffect } from 'react';
import { SkeletonChart } from '../common/SkeletonLoaders.jsx';
import TrendChart from '../common/TrendChart.jsx';
import { getNationalIndexTrend } from '../../api/govClient.js';

/**
 * NationalTrendChart — Government Dashboard Component #1
 *
 * Displays the national aggregate DGCA-weighted Udaan Metrics index trend
 * over time, using the generic TrendChart with a MoM/YoY toggle.
 *
 * Data source: getNationalIndexTrend() from govClient.js
 * Status: Live latest-day value merged with MOCK historical fill.
 */

const NationalTrendChart = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const trend = await getNationalIndexTrend();
      setData(trend);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) return <SkeletonChart height="h-72" />;

  // Calculate latest stats for the headline
  const latest = data.length > 0 ? data[data.length - 1] : null;
  const prev = data.length > 1 ? data[data.length - 2] : null;
  const change = latest && prev ? (latest.value - prev.value).toFixed(1) : null;
  const changeDir = change > 0 ? '+' : '';

  return (
    <div className="space-y-4">
      {/* Headline KPI Strip */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="border border-border bg-white p-5 border-l-4 border-l-navy col-span-1 md:col-span-2">
          <div className="text-xs font-sans text-textSecondary uppercase tracking-widest mb-1">
            National Udaan Metrics Index
          </div>
          <div className="flex items-baseline gap-3">
            <span className="font-serif text-5xl font-bold text-navy">
              {latest ? latest.value : '—'}
            </span>
            {change !== null && (
              <span className={`font-mono text-sm px-2 py-1 rounded-sm border ${
                change > 0
                  ? 'bg-red/10 text-red border-red/20'
                  : change < 0
                    ? 'bg-green/10 text-green border-green/20'
                    : 'bg-gray-100 text-textSecondary border-gray-200'
              }`}>
                {changeDir}{change} pts DoD
              </span>
            )}
          </div>
          <p className="font-sans text-xs text-textSecondary mt-2">
            DGCA-weighted composite &middot; {latest ? latest.date : ''} &middot; Base = 100
          </p>
        </div>

        <div className="border border-border bg-white p-5">
          <div className="text-xs font-sans text-textSecondary uppercase tracking-widest mb-1">OTA Premium</div>
          <div className="flex items-baseline gap-2">
            <div className="font-mono text-3xl text-red tabular-nums">
              {latest && latest.ota_premium_pct ? `+${latest.ota_premium_pct}%` : '—'}
            </div>
          </div>
          <div className="text-xs text-textSecondary mt-1">markup on platforms</div>
        </div>

        <div className="border border-border bg-white p-5">
          <div className="text-xs font-sans text-textSecondary uppercase tracking-widest mb-1">Data Points</div>
          <div className="font-mono text-3xl text-navy tabular-nums">{data.length}</div>
          <div className="text-xs text-textSecondary mt-1">consecutive days</div>
        </div>
      </div>

      {/* Trend Chart */}
      <TrendChart
        data={data}
        title="National Udaan Metrics Index — 30-Day Trend"
        subtitle="Laspeyres-style, DGCA-weighted composite (estimated placeholder weights)"
        baseValue={100}
        color="#0B2C4D"
        showToggle={true}
      />
    </div>
  );
};

export default NationalTrendChart;
