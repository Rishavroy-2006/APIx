import React, { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';

/**
 * TrendChart — Generic, reusable line chart.
 * Parameterized by data scope to serve both:
 *   1. National aggregate index trend (Government Dashboard)
 *   2. Per-route fare trajectory & baseline overlay (Citizen Dashboard)
 *
 * Props:
 *   data          — Array of items, e.g. { date: 'T+7', value: 4850, baseline?: 5100 }
 *   xAxisKey      — Property for X axis (default 'date')
 *   title         — Chart title string
 *   subtitle      — Optional subtitle note
 *   baseValue     — Optional constant reference line (default null)
 *   unit          — Optional unit label suffix (default '')
 *   valuePrefix   — Optional currency prefix (e.g. '₹')
 *   color         — Primary line color (default navy #0B2C4D)
 *   showToggle    — Show MoM/YoY toggle (default true)
 *   onToggle      — Callback when toggle changes: (mode: 'MoM' | 'YoY') => void
 *   showOverlay   — Render secondary dashed baseline line if 'baseline' key exists in data (default false)
 *   overlayLabel  — Legend/tooltip label for secondary line (default 'Seasonal Baseline')
 *   overlayColor  — Secondary line color (default saffron #E98A15)
 */

const CustomTooltip = ({ active, payload, label, unit, valuePrefix }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white border border-border p-3 text-sm font-sans shadow-sm">
        <p className="font-semibold text-navy mb-1">{label}</p>
        {payload.map((entry, idx) => (
          <p key={idx} className="text-textPrimary text-xs flex items-center justify-between gap-4">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
              {entry.name || 'Value'}:
            </span>
            <span className="font-mono font-semibold">
              {valuePrefix}{typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}{unit}
            </span>
          </p>
        ))}
      </div>
    );
  }
  return null;
};

const TrendChart = ({
  data = [],
  xAxisKey = 'date',
  title = 'Index Trend',
  subtitle = '',
  baseValue = null,
  unit = '',
  valuePrefix = '',
  color = '#0B2C4D',
  showToggle = true,
  onToggle = () => {},
  showOverlay = false,
  overlayLabel = 'Seasonal Baseline',
  overlayColor = '#E98A15',
}) => {
  const [mode, setMode] = useState('MoM');

  const handleToggle = (newMode) => {
    setMode(newMode);
    onToggle(newMode);
  };

  const values = [];
  data.forEach(d => {
    if (typeof d.value === 'number') values.push(d.value);
    if (showOverlay && typeof d.baseline === 'number') values.push(d.baseline);
  });

  const minVal = values.length > 0 ? Math.min(...values) : 0;
  const maxVal = values.length > 0 ? Math.max(...values) : 100;
  const padding = Math.max((maxVal - minVal) * 0.12, 10);

  return (
    <div className="bg-white border border-border p-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between mb-1 gap-2">
        <h3 className="font-serif text-xl text-navy">{title}</h3>
        {showToggle && (
          <div className="flex gap-1 bg-bg border border-border p-1 rounded-sm">
            {['MoM', 'YoY'].map(m => (
              <button
                key={m}
                onClick={() => handleToggle(m)}
                className={`px-3 py-1 text-xs font-sans font-medium transition-colors rounded-sm ${
                  mode === m
                    ? 'bg-navy text-white'
                    : 'text-textSecondary hover:text-navy'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        )}
      </div>
      {subtitle && (
        <p className="text-xs text-textSecondary font-sans mb-4">{subtitle}</p>
      )}

      {/* Legend if overlay enabled */}
      {showOverlay && (
        <div className="flex items-center gap-6 mb-4 text-xs font-sans">
          <span className="flex items-center gap-2">
            <span className="w-3 h-0.5" style={{ backgroundColor: color }} />
            <span className="font-medium text-navy">Current Fare Trajectory</span>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-0.5 border-t border-dashed" style={{ borderColor: overlayColor }} />
            <span className="text-textSecondary">{overlayLabel}</span>
          </span>
        </div>
      )}

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 15, bottom: 5, left: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#D9DEE5" />
            <XAxis
              dataKey={xAxisKey}
              tick={{ fontSize: 12, fill: '#5B6472' }}
              tickMargin={10}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              tick={{ fontSize: 12, fill: '#5B6472' }}
              axisLine={false}
              tickLine={false}
              domain={[Math.max(0, Math.floor(minVal - padding)), Math.ceil(maxVal + padding)]}
              tickFormatter={v => `${valuePrefix}${v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v}`}
              width={55}
            />
            <Tooltip content={<CustomTooltip unit={unit} valuePrefix={valuePrefix} />} />
            {baseValue !== null && (
              <ReferenceLine
                y={baseValue}
                stroke="#E98A15"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{ value: `Base ${baseValue}`, position: 'insideTopRight', fill: '#E98A15', fontSize: 11, fontFamily: 'Inter' }}
              />
            )}
            <Line
              type="monotone"
              name="Current Fare"
              dataKey="value"
              stroke={color}
              strokeWidth={2.5}
              dot={{ fill: color, strokeWidth: 2, r: 4 }}
              activeDot={{ r: 6, fill: color }}
              isAnimationActive={true}
              animationDuration={600}
            />
            {showOverlay && (
              <Line
                type="monotone"
                name={overlayLabel}
                dataKey="baseline"
                stroke={overlayColor}
                strokeWidth={2}
                strokeDasharray="5 5"
                dot={{ fill: overlayColor, r: 3 }}
                activeDot={{ r: 5 }}
                isAnimationActive={true}
                animationDuration={600}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex justify-center mt-4 text-xs font-sans text-textSecondary italic">
        Showing {data.length} window data points &middot; {showToggle ? (mode === 'YoY' ? 'Year-over-Year baseline' : 'Month-over-Month trajectory') : 'Trajectory curve'}
      </div>
    </div>
  );
};

export default TrendChart;
