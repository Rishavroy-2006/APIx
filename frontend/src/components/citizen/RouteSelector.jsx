import React from 'react';

/**
 * RouteSelector — Citizen Dashboard Component #1
 *
 * Route selector dropdown & pill selector over our fixed 6-route list
 * (Air India Express descoped per requirements).
 *
 * Props:
 *   selectedRoute — string (e.g. 'DEL-BOM')
 *   onSelectRoute — function (route: string) => void
 */

const ROUTES = [
  { code: 'DEL-BOM', origin: 'Delhi (DEL)', destination: 'Mumbai (BOM)', name: 'Delhi ↔ Mumbai' },
  { code: 'DEL-BLR', origin: 'Delhi (DEL)', destination: 'Bengaluru (BLR)', name: 'Delhi ↔ Bengaluru' },
  { code: 'BOM-BLR', origin: 'Mumbai (BOM)', destination: 'Bengaluru (BLR)', name: 'Mumbai ↔ Bengaluru' },
  { code: 'DEL-CCU', origin: 'Delhi (DEL)', destination: 'Kolkata (CCU)', name: 'Delhi ↔ Kolkata' },
  { code: 'BLR-HYD', origin: 'Bengaluru (BLR)', destination: 'Hyderabad (HYD)', name: 'Bengaluru ↔ Hyderabad' },
  { code: 'MAA-DEL', origin: 'Chennai (MAA)', destination: 'Delhi (DEL)', name: 'Chennai ↔ Delhi' },
];

const RouteSelector = ({ selectedRoute = 'DEL-BOM', onSelectRoute = () => {} }) => {
  const current = ROUTES.find(r => r.code === selectedRoute) || ROUTES[0];

  return (
    <div className="bg-white border border-border p-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <label className="block text-xs font-sans uppercase tracking-widest text-textSecondary mb-1 font-semibold">
            Select Flight Corridor
          </label>
          <div className="flex items-center gap-3">
            <span className="font-serif text-2xl font-bold text-navy">{current.name}</span>
            <span className="font-mono text-xs px-2 py-1 bg-bg border border-border rounded-sm text-textSecondary font-semibold">
              {current.code}
            </span>
          </div>
        </div>

        {/* Dropdown for mobile & explicit selection */}
        <div className="w-full md:w-72">
          <select
            value={selectedRoute}
            onChange={(e) => onSelectRoute(e.target.value)}
            className="w-full border border-border bg-bg px-4 py-2.5 font-sans text-sm font-medium text-navy focus:outline-none focus:ring-2 focus:ring-navy focus:border-navy cursor-pointer transition-all"
          >
            {ROUTES.map(r => (
              <option key={r.code} value={r.code}>
                {r.code} — {r.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Quick pill selector bar */}
      <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-border">
        {ROUTES.map(r => (
          <button
            key={r.code}
            onClick={() => onSelectRoute(r.code)}
            className={`px-3 py-1.5 text-xs font-mono font-medium transition-colors border rounded-sm ${
              selectedRoute === r.code
                ? 'bg-navy text-white border-navy shadow-xs'
                : 'bg-bg text-textSecondary border-border hover:border-navy hover:text-navy'
            }`}
          >
            {r.code}
          </button>
        ))}
      </div>
    </div>
  );
};

export { ROUTES };
export default RouteSelector;
