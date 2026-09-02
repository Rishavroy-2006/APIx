import React, { useState, useEffect } from 'react';
import { getRouteHeatmapData, getVolatilityData } from '../../api/govClient.js';
import VolatilitySignal from './VolatilitySignal.jsx';

/**
 * RouteHeatmap — Government Dashboard Component #4
 *
 * DECISION: Sortable clean table instead of react-simple-maps India map.
 *
 * WHY: A map visualization of 6 city-pair routes (not states/regions)
 * requires a custom GeoJSON with arc overlays between airports — fiddly
 * to render correctly and easy to break visually in a live demo. A clean,
 * sortable, audit-ready table beats a visually broken map, especially
 * for a government audience that needs precise numbers, not approximate
 * geography. The map can be added as a polish layer post-demo.
 *
 * Features:
 *   - Sortable by any column (click header to toggle asc/desc)
 *   - Directional color-coding (red = price up, green = down)
 *   - Embedded VolatilitySignal badges per route
 *   - DGCA weight column for transparency
 *
 * Data source: getRouteHeatmapData() from govClient.js (REAL from /api/index/heatmap)
 */

const SortIcon = ({ active, direction }) => (
  <span className="inline-flex flex-col ml-1 text-[8px] leading-none">
    <span className={active && direction === 'asc' ? 'text-navy' : 'text-gray-300'}>▲</span>
    <span className={active && direction === 'desc' ? 'text-navy' : 'text-gray-300'}>▼</span>
  </span>
);

const RouteHeatmap = () => {
  const [data, setData] = useState([]);
  const [volatilityMap, setVolatilityMap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sortKey, setSortKey] = useState('pct_change');
  const [sortDir, setSortDir] = useState('desc');

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [heatmap, volatility] = await Promise.all([
        getRouteHeatmapData(),
        getVolatilityData(),
      ]);
      setData(heatmap);
      setVolatilityMap(volatility);
      setLoading(false);
    }
    load();
  }, []);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = [...data].sort((a, b) => {
    let aVal = a[sortKey];
    let bVal = b[sortKey];
    if (typeof aVal === 'string') aVal = aVal.toLowerCase();
    if (typeof bVal === 'string') bVal = bVal.toLowerCase();
    if (aVal == null) return 1;
    if (bVal == null) return -1;
    if (sortDir === 'asc') return aVal > bVal ? 1 : -1;
    return aVal < bVal ? 1 : -1;
  });

  if (loading) {
    return (
      <div className="bg-white border border-border p-6">
        <div className="h-48 flex items-center justify-center">
          <p className="font-sans text-sm text-textSecondary animate-pulse">Loading route heatmap...</p>
        </div>
      </div>
    );
  }

  const columns = [
    { key: 'route', label: 'Corridor', align: 'left' },
    { key: 'weight', label: 'DGCA Weight', align: 'right' },
    { key: 'current_fare', label: 'Median Fare (₹)', align: 'right' },
    { key: 'pct_change', label: 'DoD Change', align: 'right' },
    { key: 'yoyChange', label: 'YoY Change', align: 'right' },
    { key: 'volatility', label: 'Volatility', align: 'center' },
  ];

  return (
    <div className="bg-white border border-border overflow-hidden">
      <div className="p-5 bg-bg border-b border-border flex flex-col md:flex-row justify-between items-start md:items-center gap-2">
        <div>
          <h3 className="font-serif text-xl text-navy">Sector-Wise Route Intelligence</h3>
          <p className="text-xs text-textSecondary font-sans mt-1">
            Click any column header to sort &middot; Color-coded by price direction
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-sans text-textSecondary">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red" /> Price Up</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green" /> Price Down</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-gray-400" /> Flat</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left font-sans text-sm">
          <thead className="bg-white border-b border-border text-textSecondary">
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => col.key !== 'volatility' && handleSort(col.key)}
                  className={`px-5 py-3 font-medium uppercase tracking-wider text-xs ${
                    col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''
                  } ${col.key !== 'volatility' ? 'cursor-pointer hover:text-navy select-none' : ''}`}
                >
                  {col.label}
                  {col.key !== 'volatility' && (
                    <SortIcon active={sortKey === col.key} direction={sortDir} />
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((row, i) => {
              const cv = volatilityMap ? volatilityMap[row.route] : null;
              return (
                <tr key={row.route} className="hover:bg-bg transition-colors">
                  <td className="px-5 py-3">
                    <span className="font-mono font-semibold text-navy">{row.route}</span>
                  </td>
                  <td className="px-5 py-3 font-mono tabular-nums text-right text-textSecondary">
                    {(row.weight * 100).toFixed(0)}%
                  </td>
                  <td className="px-5 py-3 font-mono tabular-nums text-right">
                    ₹{row.current_fare?.toLocaleString()}
                  </td>
                  <td className={`px-5 py-3 font-mono tabular-nums text-right font-medium ${
                    row.pct_change > 0 ? 'text-red' : row.pct_change < 0 ? 'text-green' : 'text-textSecondary'
                  }`}>
                    {row.pct_change === 0 ? '—' : `${row.pct_change > 0 ? '+' : ''}${row.pct_change}%`}
                  </td>
                  <td className="px-5 py-3 font-mono tabular-nums text-right text-textSecondary italic text-xs">
                    {row.yoyChange !== null ? `${row.yoyChange > 0 ? '+' : ''}${row.yoyChange}%` : 'Insufficient history'}
                  </td>
                  <td className="px-5 py-3 text-center">
                    <VolatilitySignal volatilityCV={cv} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="px-5 py-3 bg-bg border-t border-border text-xs font-sans text-textSecondary italic">
        Heatmap format: Sortable table (chosen over India map for data precision in government demos) &middot; YoY requires &gt;365d of collection history
      </div>
    </div>
  );
};

export default RouteHeatmap;
