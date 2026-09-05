import React from 'react';

/**
 * SeasonalBaselineOverlay — Citizen Dashboard Component #3
 *
 * Toggle control that overlay/hides the historical seasonal baseline curve
 * on top of the current fare trajectory chart.
 *
 * Data note:
 *   // MOCK — replace once A.3 event tagging + baseline data are live
 *
 * Props:
 *   enabled   — boolean
 *   onToggle  — function (enabled: boolean) => void
 */

const SeasonalBaselineOverlay = ({ enabled = false, onToggle = () => {} }) => {
  return (
    <div className="flex items-center justify-between bg-bg border border-border p-3 rounded-sm">
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full bg-saffron" />
        <div>
          <span className="font-sans text-xs font-semibold text-navy">Seasonal Baseline Overlay</span>
          <span className="ml-2 font-mono text-[10px] text-textSecondary bg-saffron/10 text-saffron px-1.5 py-0.5 rounded-sm border border-saffron/20">
            Derived from Historical Trajectories
          </span>
        </div>
      </div>

      <button
        onClick={() => onToggle(!enabled)}
        className={`px-3 py-1 text-xs font-sans font-medium transition-colors border rounded-sm ${
          enabled
            ? 'bg-saffron text-white border-saffron shadow-xs'
            : 'bg-white text-textSecondary border-border hover:border-saffron hover:text-saffron'
        }`}
      >
        {enabled ? 'Hide Baseline' : 'Show Baseline'}
      </button>
    </div>
  );
};

export default SeasonalBaselineOverlay;
