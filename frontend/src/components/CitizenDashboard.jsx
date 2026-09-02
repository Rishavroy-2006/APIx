import React, { useState } from 'react';
import RouteSelector from './citizen/RouteSelector.jsx';
import FareTrajectoryChart from './citizen/FareTrajectoryChart.jsx';
import BookNowWaitSignal from './citizen/BookNowWaitSignal.jsx';
import AlertsSignup from './citizen/AlertsSignup.jsx';

/**
 * CitizenDashboard — Main container for the Citizen / Traveller Fare Intelligence Portal
 *
 * Answers: "Should I book now or wait?"
 *
 * Components rendered in order:
 *   1. RouteSelector — Dropdown/pill selector over the 6 active DGCA corridors
 *   2. BookNowWaitSignal — Traffic-light decision badge (Green / Amber / Red)
 *   3. FareTrajectoryChart — Single-route T+1..T+45 trajectory chart with SeasonalBaselineOverlay toggle
 *   4. AlertsSignup — Price alert subscription form UI (disabled prototype state)
 */

const CitizenDashboard = () => {
  const [selectedRoute, setSelectedRoute] = useState('DEL-BOM');

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 animate-fade-in">

      {/* Portal Header */}
      <div className="border-b border-border pb-6">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="bg-steel text-white font-mono text-xs px-2 py-1 rounded-sm uppercase tracking-wider">
                Citizen Portal
              </span>
              <span className="bg-green/10 text-green font-sans text-xs px-2 py-1 rounded-sm border border-green/20 uppercase tracking-wider">
                Live Data
              </span>
            </div>
            <h2 className="font-serif text-3xl text-navy">
              Personalized Airfare Trajectory & Decision Portal
            </h2>
            <p className="font-sans text-sm text-textSecondary mt-1">
              Track route-level fare trajectories against historical baselines and know when to book.
            </p>
          </div>

          <div className="text-xs font-sans text-textSecondary">
            Active Corridor: <span className="font-mono text-navy font-bold">{selectedRoute}</span>
          </div>
        </div>
      </div>

      {/* 1. Corridor Selector */}
      <RouteSelector
        selectedRoute={selectedRoute}
        onSelectRoute={setSelectedRoute}
      />

      {/* 2. Traffic Light Book Now vs Wait Signal */}
      <BookNowWaitSignal
        selectedRoute={selectedRoute}
      />

      {/* 3. Fare Trajectory Chart + Seasonal Baseline Overlay */}
      <FareTrajectoryChart
        selectedRoute={selectedRoute}
      />

      {/* 4. Price Alert Subscription UI */}
      <AlertsSignup
        selectedRoute={selectedRoute}
      />

      {/* Portal Footer Note */}
      <div className="text-xs font-sans text-textSecondary border-t border-border pt-4 flex flex-col md:flex-row justify-between gap-2">
        <span>
          APIx Citizen Portal &middot; SIH Problem Statement 26056
        </span>
        <span className="italic">
          Fare quotes updated daily &middot; Trailing medians computed across active capture runs
        </span>
      </div>

    </div>
  );
};

export default CitizenDashboard;
