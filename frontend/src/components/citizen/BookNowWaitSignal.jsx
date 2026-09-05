import React, { useState, useEffect } from 'react';
import { SkeletonText, SkeletonCard } from '../common/SkeletonLoaders.jsx';
import { getRouteSignalData } from '../../api/govClient.js';

/**
 * BookNowWaitSignal — Citizen Dashboard Component #4
 *
 * Traffic-light decision badge (Green / Amber / Red) comparing today's
 * median fare for the selected route against its trailing seasonal median.
 *
 * CRITICAL RULE:
 *   Labeled explicitly as "based on historical pattern (rule-based indicator)"
 *   so users do not mistake it for an ML predictive forecast.
 *
 * Props:
 *   selectedRoute — string (e.g. 'DEL-BOM')
 */

const BookNowWaitSignal = ({ selectedRoute = 'DEL-BOM' }) => {
  const [signalData, setSignalData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const data = await getRouteSignalData(selectedRoute);
      setSignalData(data);
      setLoading(false);
    }
    load();
  }, [selectedRoute]);

  if (loading || !signalData) {
    return (
      <div className="bg-white border border-border p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="space-y-2 flex-grow w-full max-w-md">
          <SkeletonText className="h-5 w-1/3" />
          <SkeletonText className="h-3 w-3/4" />
        </div>
        <div className="flex gap-4">
          <SkeletonCard height="h-20" className="w-32" />
          <SkeletonCard height="h-20" className="w-32" />
        </div>
      </div>
    );
  }

  const { signal, label, recommendation, currentFare, trailingMedian, diffPct, bgClass, dotClass } = signalData;

  return (
    <div className="bg-white border border-border p-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        {/* Signal Badge & Decision */}
        <div className="flex items-center gap-4">
          <div className={`w-14 h-14 rounded-full flex items-center justify-center border-2 ${bgClass}`}>
            <span className={`w-6 h-6 rounded-full ${dotClass} animate-pulse`} />
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2.5 py-0.5 text-xs font-sans font-bold uppercase tracking-wider border rounded-sm ${bgClass}`}>
                {label}
              </span>
              <span className="text-xs font-mono text-textSecondary">
                ({diffPct > 0 ? '+' : ''}{diffPct}% vs trailing median)
              </span>
            </div>
            <h3 className="font-serif text-xl text-navy">
              Booking Recommendation — {selectedRoute}
            </h3>
          </div>
        </div>

        {/* Price Comparison Block */}
        <div className="flex gap-6 border-t md:border-t-0 md:border-l border-border pt-4 md:pt-0 md:pl-6 text-sm font-sans">
          <div>
            <span className="text-xs text-textSecondary uppercase tracking-wider block">Current Fare</span>
            <span className="font-mono text-lg font-bold text-navy">₹{currentFare?.toLocaleString()}</span>
          </div>
          <div>
            <span className="text-xs text-textSecondary uppercase tracking-wider block">Trailing Median</span>
            <span className="font-mono text-lg font-semibold text-textSecondary">₹{trailingMedian?.toLocaleString()}</span>
          </div>
        </div>
      </div>

      {/* Recommendation Narrative */}
      <div className="mt-4 p-4 bg-bg border border-border rounded-sm">
        <p className="font-sans text-sm text-textPrimary font-medium">
          {recommendation}
        </p>
      </div>

      {/* Mandatory Disclaimer Badge */}
      <div className="mt-3 flex items-center gap-1.5 text-[11px] font-sans text-textSecondary italic">
        <svg className="w-3.5 h-3.5 text-saffron shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Rule-based indicator based on historical trailing pattern &middot; Not a predictive forecast model
      </div>
    </div>
  );
};

export default BookNowWaitSignal;
