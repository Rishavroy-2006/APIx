import React from 'react';
import { useNavigate } from 'react-router-dom';
import { SkeletonPage } from './common/SkeletonLoaders.jsx';

const StatCard = ({ label, value }) => (
  <div className="border border-border bg-white p-6 flex flex-col justify-between hover:shadow-md transition-shadow">
    <div className="text-textSecondary text-xs uppercase tracking-wider font-sans mb-4">{label}</div>
    <div className="font-mono text-3xl text-navy tabular-nums text-right">{value}</div>
  </div>
);

const OverviewTab = ({ indexData, setActiveTab }) => {
  const navigate = useNavigate();
  if (!indexData) return <SkeletonPage />;

  return (
    <div className="max-w-6xl mx-auto px-6 py-12 space-y-12 animate-fade-in">
      
      {/* Headline Stat Card */}
      <div className="border border-border bg-white p-8 border-l-4 border-l-navy flex flex-col md:flex-row justify-between items-start md:items-end">
        <div>
          <div className="text-xs font-sans text-textSecondary uppercase tracking-widest mb-2">UDAAN METRICS TODAY</div>
          <div className="flex items-baseline gap-4">
            <h2 className="font-serif text-6xl font-bold text-navy">{indexData.value}</h2>
            <span className="font-mono text-xs uppercase bg-bg text-textSecondary px-2 py-1 rounded-sm border border-border">
              LIVE DATA (PROVISIONAL)
            </span>
          </div>
          <p className="font-sans text-sm text-textSecondary mt-4">
            Monitoring {indexData.carriers.length} Carriers across {indexData.routes_tracked} Routes &middot; {indexData.days_live} Days of Live Data
          </p>
        </div>
      </div>

      {/* Problem Paragraph */}
      <p className="font-sans text-lg leading-relaxed text-textPrimary max-w-4xl">
        India's CPI still relies on periodic manual checks for airfares, failing to capture extreme intra-day volatility. Udaan Metrics scrapes real carrier fares daily to compute an accurate, real-time index.
      </p>

      {/* Stat Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatCard label="Routes Tracked" value={indexData.routes_tracked} />
        <StatCard label="Days of Live Collection" value={indexData.days_live} />
        <StatCard label="Advance-Purchase Windows" value={indexData.advance_windows} />
      </div>

      {/* Pull Quote */}
      <blockquote className="border-l-4 border-l-saffron pl-6 py-2 bg-white border-y border-r border-y-border border-r-border my-8 shadow-sm">
        <p className="font-serif italic text-lg leading-relaxed text-navy max-w-3xl">
          "Right now, India's official inflation number treats airfares like it's still 2005 — a few manual price checks a month, even though fares swing 300% in a single day. The Laspeyres-style index computation engine is fully built and actively weights routes against a configuration file (DGCA_ROUTE_WEIGHTS). For this demo, the file is populated with estimated placeholder weights (e.g., DEL-BOM at 25%), not yet sourced from an official DGCA traffic report. In production, MoSPI would populate this config with exact passenger-volume figures from official monthly DGCA traffic reports to yield the verified index."
        </p>
      </blockquote>

      {/* Link to Live Data */}
      <div>
        <button 
          onClick={() => navigate('/live-data')}
          className="font-sans text-navy font-semibold hover:text-steel transition-colors group flex items-center gap-2 py-2 px-4 -ml-4 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-navy"
        >
          See the live pipeline <span className="group-hover:translate-x-1 transition-transform">&rarr;</span>
        </button>
      </div>
      
    </div>
  );
};

export default OverviewTab;
