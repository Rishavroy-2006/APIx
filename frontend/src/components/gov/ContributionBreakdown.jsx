import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getRouteContribution } from '../../api/govClient.js';

/**
 * ContributionBreakdown — Government Dashboard Component #3
 *
 * Horizontal bar chart ranking routes by their contribution to
 * the current month's composite index movement.
 *
 * Contribution_i = W_i × ΔP_i (DGCA weight × median fare)
 * normalized to percentage shares.
 *
 * Data source: getRouteContribution() from govClient.js
 * Status: REAL when /api/fares/raw returns data, MOCK fallback otherwise.
 *
 * NOTE: Event/festival tagging is NOT a blocker — it gets added as a
 * later enhancement overlay, not as a dependency of this component.
 */

const ROUTE_COLORS = {
  'DEL-BOM': '#0B2C4D',
  'DEL-BLR': '#1B4B75',
  'BOM-BLR': '#2D6A9F',
  'DEL-CCU': '#E98A15',
  'BLR-HYD': '#138762',
  'MAA-DEL': '#5B6472',
};

const CustomTooltip = ({ active, payload }) => {
  if (active && payload && payload.length) {
    const d = payload[0].payload;
    return (
      <div className="bg-white border border-border p-3 text-sm font-sans shadow-sm">
        <p className="font-semibold text-navy mb-1">{d.route}</p>
        <p className="text-textPrimary">Contribution: <span className="font-mono">{d.contribution}%</span></p>
        <p className="text-textSecondary text-xs">Median Fare: <span className="font-mono">₹{d.medianFare?.toLocaleString()}</span></p>
        <p className="text-textSecondary text-xs">DGCA Weight: <span className="font-mono">{(d.weight * 100).toFixed(0)}%</span></p>
      </div>
    );
  }
  return null;
};

const ContributionBreakdown = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const contributions = await getRouteContribution();
      setData(contributions);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="bg-white border border-border p-6">
        <div className="h-64 flex items-center justify-center">
          <p className="font-sans text-sm text-textSecondary animate-pulse">Computing contribution breakdown...</p>
        </div>
      </div>
    );
  }

  const topRoute = data.length > 0 ? data[0] : null;

  return (
    <div className="bg-white border border-border p-6">
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-1 gap-2">
        <div>
          <h3 className="font-serif text-xl text-navy">Route Contribution to Index Movement</h3>
          <p className="text-xs text-textSecondary font-sans mt-1">
            Contribution<sub>i</sub> = W<sub>i</sub> × MedianFare<sub>i</sub> &middot; Ranked by weighted share
          </p>
        </div>
        {topRoute && (
          <div className="flex items-baseline gap-2 bg-bg border border-border px-3 py-2 rounded-sm">
            <span className="text-xs text-textSecondary font-sans uppercase tracking-wider">Top Driver:</span>
            <span className="font-mono text-sm font-semibold text-navy">{topRoute.route}</span>
            <span className="font-mono text-sm text-saffron">{topRoute.contribution}%</span>
          </div>
        )}
      </div>

      <div className="h-72 mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#D9DEE5" />
            <XAxis
              type="number"
              tick={{ fontSize: 12, fill: '#5B6472' }}
              axisLine={false}
              tickLine={false}
              tickFormatter={v => `${v}%`}
              domain={[0, 'auto']}
            />
            <YAxis
              type="category"
              dataKey="route"
              tick={{ fontSize: 13, fill: '#1C2530', fontFamily: 'JetBrains Mono' }}
              axisLine={false}
              tickLine={false}
              width={75}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="contribution" radius={[0, 3, 3, 0]} barSize={28}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={ROUTE_COLORS[entry.route] || '#1B4B75'}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Legend / Table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left font-sans text-sm">
          <thead className="border-b border-border text-textSecondary">
            <tr>
              <th className="pb-2 font-medium uppercase text-xs">Route</th>
              <th className="pb-2 font-medium uppercase text-xs text-right">DGCA Weight</th>
              <th className="pb-2 font-medium uppercase text-xs text-right">Median Fare</th>
              <th className="pb-2 font-medium uppercase text-xs text-right">Contribution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.map((d, i) => (
              <tr key={d.route} className="hover:bg-bg transition-colors">
                <td className="py-2 flex items-center gap-2">
                  <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: ROUTE_COLORS[d.route] || '#1B4B75' }} />
                  <span className="font-mono text-navy">{d.route}</span>
                </td>
                <td className="py-2 font-mono tabular-nums text-right text-textSecondary">{(d.weight * 100).toFixed(0)}%</td>
                <td className="py-2 font-mono tabular-nums text-right">₹{d.medianFare?.toLocaleString()}</td>
                <td className="py-2 font-mono tabular-nums text-right font-medium text-navy">{d.contribution}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ContributionBreakdown;
