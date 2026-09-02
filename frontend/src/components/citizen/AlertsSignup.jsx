import React, { useState } from 'react';

/**
 * AlertsSignup — Citizen Dashboard Component #5
 *
 * Price alert subscription form UI for Telegram / Email notifications.
 *
 * CRITICAL RULE:
 *   UI ONLY — no backend wiring. Submit button disabled with a clear
 *   "Coming Soon" badge. Does NOT fabricate fake success messages on submit.
 *
 * Props:
 *   selectedRoute — string (e.g. 'DEL-BOM')
 */

const AlertsSignup = ({ selectedRoute = 'DEL-BOM' }) => {
  const [channel, setChannel] = useState('email');
  const [contactInput, setContactInput] = useState('');
  const [thresholdInput, setThresholdInput] = useState('');

  return (
    <div className="bg-white border border-border p-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 mb-4 border-b border-border gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-serif text-xl text-navy">Price Alert Subscription</h3>
            <span className="bg-saffron/10 text-saffron font-mono text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-sm border border-saffron/20">
              Coming Soon
            </span>
          </div>
          <p className="font-sans text-xs text-textSecondary mt-1">
            Get instant Telegram or Email notifications when fares on <span className="font-mono text-navy font-semibold">{selectedRoute}</span> drop below your target price.
          </p>
        </div>
      </div>

      <form onSubmit={(e) => e.preventDefault()} className="space-y-4">
        {/* Channel Selection Toggle */}
        <div className="flex gap-4 items-center">
          <label className="text-xs font-sans text-textSecondary uppercase tracking-wider font-semibold">
            Notification Channel:
          </label>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setChannel('email')}
              className={`px-3 py-1 text-xs font-sans font-medium transition-colors border rounded-sm ${
                channel === 'email'
                  ? 'bg-navy text-white border-navy'
                  : 'bg-bg text-textSecondary border-border'
              }`}
            >
              Email
            </button>
            <button
              type="button"
              onClick={() => setChannel('telegram')}
              className={`px-3 py-1 text-xs font-sans font-medium transition-colors border rounded-sm ${
                channel === 'telegram'
                  ? 'bg-navy text-white border-navy'
                  : 'bg-bg text-textSecondary border-border'
              }`}
            >
              Telegram
            </button>
          </div>
        </div>

        {/* Input Fields */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-sans text-textSecondary uppercase tracking-wider mb-1">
              {channel === 'email' ? 'Email Address' : 'Telegram Handle / ID'}
            </label>
            <input
              type={channel === 'email' ? 'email' : 'text'}
              disabled
              value={contactInput}
              onChange={(e) => setContactInput(e.target.value)}
              placeholder={channel === 'email' ? 'you@example.com (Notifications disabled in prototype)' : '@yourhandle'}
              className="w-full border border-border bg-gray-100 px-4 py-2.5 font-sans text-sm text-textSecondary cursor-not-allowed outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-sans text-textSecondary uppercase tracking-wider mb-1">
              Target Price Threshold (₹)
            </label>
            <input
              type="number"
              disabled
              value={thresholdInput}
              onChange={(e) => setThresholdInput(e.target.value)}
              placeholder="e.g. 4500 (Notifications disabled in prototype)"
              className="w-full border border-border bg-gray-100 px-4 py-2.5 font-sans text-sm text-textSecondary cursor-not-allowed outline-none"
            />
          </div>
        </div>

        {/* Submit Button — Explicitly Disabled */}
        <div className="pt-2 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
          <button
            type="button"
            disabled
            className="bg-gray-300 text-gray-600 font-sans font-medium px-6 py-2.5 text-sm cursor-not-allowed rounded-sm border border-gray-400 opacity-80"
          >
            Subscribe to Price Alerts (Disabled in Prototype)
          </button>

          <span className="text-xs font-sans text-textSecondary italic">
            Automated alerts will be activated once the notification backend goes live.
          </span>
        </div>
      </form>
    </div>
  );
};

export default AlertsSignup;
