import React from 'react';

/**
 * VolatilitySignal — Government Dashboard Component #5
 *
 * Small colored badge per route, flagging volatility / monopoly risk.
 *
 * TODO: pending backend calc — the pipeline does not yet compute
 * coefficient of variation (σ/μ) per route per day. Once it does,
 * replace the stub logic below with real thresholds.
 *
 * Current behavior:
 *   - If volatilityCV is provided and numeric, use threshold logic
 *   - If volatilityCV is null/undefined, show "Pending" placeholder
 *
 * Thresholds (illustrative, calibrate against real data):
 *   CV < 0.15  → STABLE (green)
 *   CV 0.15–0.30 → ELEVATED (yellow/saffron)
 *   CV > 0.30  → HIGH VOLATILITY (red)
 */

const VolatilitySignal = ({ volatilityCV = null }) => {
  // TODO: pending backend calc — replace stub once pipeline provides real CV
  if (volatilityCV === null || volatilityCV === undefined) {
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-sans font-medium uppercase tracking-wider bg-gray-100 text-textSecondary border border-gray-200 rounded-sm cursor-help"
        title="Volatility metric pending backend computation (σ/μ per route per day)"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
        Pending
      </span>
    );
  }

  let label, dotClass, bgClass;

  if (volatilityCV < 0.15) {
    label = 'Stable';
    dotClass = 'bg-green';
    bgClass = 'bg-green/10 text-green border-green/20';
  } else if (volatilityCV < 0.30) {
    label = 'Elevated';
    dotClass = 'bg-saffron';
    bgClass = 'bg-saffron/10 text-saffron border-saffron/20';
  } else {
    label = 'High Risk';
    dotClass = 'bg-red';
    bgClass = 'bg-red/10 text-red border-red/20';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-sans font-medium uppercase tracking-wider border rounded-sm ${bgClass}`}
      title={`Coefficient of Variation: ${volatilityCV.toFixed(3)}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClass}`} />
      {label}
    </span>
  );
};

export default VolatilitySignal;
