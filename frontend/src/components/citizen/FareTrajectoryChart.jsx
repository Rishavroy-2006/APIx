import React, { useState, useEffect } from 'react';
import TrendChart from '../common/TrendChart.jsx';
import SeasonalBaselineOverlay from './SeasonalBaselineOverlay.jsx';
import { getRouteTrajectoryData, getSeasonalBaselineData } from '../../api/govClient.js';

/**
 * FareTrajectoryChart — Citizen Dashboard Component #2 & #3
 *
 * Reuses generic TrendChart component, parameterized for a single route's
 * T+1 -> T+45 advance purchase fare trajectory.
 *
 * Integrates SeasonalBaselineOverlay toggle to overlay the historical
 * seasonal baseline line.
 *
 * Props:
 *   selectedRoute — string (e.g. 'DEL-BOM')
 */

const FareTrajectoryChart = ({ selectedRoute = 'DEL-BOM' }) => {
  const [chartData, setChartData] = useState([]);
  const [showBaseline, setShowBaseline] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [trajectory, baseline] = await Promise.all([
        getRouteTrajectoryData(selectedRoute),
        getSeasonalBaselineData(selectedRoute), // MOCK baseline pending A.3
      ]);

      // Merge trajectory values with baseline overlay values by window
      const merged = trajectory.map(t => {
        const b = baseline.find(item => item.window === t.window);
        return {
          ...t,
          baseline: b ? b.baseline : null,
        };
      });

      setChartData(merged);
      setLoading(false);
    }
    load();
  }, [selectedRoute]);

  if (loading) {
    return (
      <div className="bg-white border border-border p-6">
        <div className="h-64 flex items-center justify-center">
          <p className="font-sans text-sm text-textSecondary animate-pulse">Loading fare trajectory for {selectedRoute}...</p>
        </div>
      </div>
    );
  }

  const currentT15 = chartData.find(d => d.window === 'T+15')?.value;
  const currentT45 = chartData.find(d => d.window === 'T+45')?.value;

  return (
    <div className="space-y-4">
      {/* Baseline Overlay Control Header */}
      <SeasonalBaselineOverlay
        enabled={showBaseline}
        onToggle={setShowBaseline}
      />

      {/* Main Fare Trajectory Chart (Reusing generic TrendChart) */}
      <TrendChart
        data={chartData}
        xAxisKey="date"
        title={`Fare Trajectory — ${selectedRoute}`}
        subtitle="Median fare across advance booking windows (T+1 to T+45 days ahead)"
        valuePrefix="₹"
        color="#0B2C4D"
        showToggle={false}
        showOverlay={showBaseline}
        overlayLabel="Seasonal Baseline (Mocked)"
        overlayColor="#E98A15"
      />

      {/* Trajectory Key Takeaway Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 font-sans text-xs">
        {chartData.map(d => (
          <div key={d.window} className="bg-white border border-border p-3 flex flex-col">
            <span className="text-textSecondary font-semibold uppercase">{d.window} Window</span>
            <span className="font-mono text-navy font-bold text-base mt-1">₹{d.value?.toLocaleString()}</span>
            {showBaseline && d.baseline && (
              <span className="text-[10px] text-textSecondary mt-0.5">
                Baseline: ₹{d.baseline.toLocaleString()}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default FareTrajectoryChart;
