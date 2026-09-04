import React from 'react';


const MethodologyTab = () => {
  const latestDate = new Date().toISOString().slice(0, 10);

  return (
    <div className="max-w-4xl mx-auto px-6 py-12 space-y-12 animate-fade-in">
      
      {/* Data Sources */}
      <section className="bg-white border border-border p-8">
        <h2 className="font-serif text-3xl text-navy mb-6">Data Sources</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-sans text-sm">
            <thead className="border-b border-border text-textSecondary">
              <tr>
                <th className="pb-3 font-medium uppercase text-xs">Source Name</th>
                <th className="pb-3 font-medium uppercase text-xs">Provision</th>
                <th className="pb-3 font-medium uppercase text-xs">Citation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              <tr>
                <td className="py-4 text-textPrimary font-medium">IndiGo Fare Search</td>
                <td className="py-4 text-textSecondary">Real-time economy seat inventory</td>
                <td className="py-4 font-mono text-steel">goindigo.in</td>
              </tr>
              <tr>
                <td className="py-4 text-textPrimary font-medium">SpiceJet Fare Search</td>
                <td className="py-4 text-textSecondary">Real-time economy seat inventory</td>
                <td className="py-4 font-mono text-steel">spicejet.com</td>
              </tr>

              <tr>
                <td className="py-4 text-textPrimary font-medium">MoSPI CPI Transport</td>
                <td className="py-4 text-textSecondary">Historical baseline alignment data</td>
                <td className="py-4 font-mono text-steel">esankhyiki.mospi.gov.in</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Sampling Protocol */}
      <section className="bg-steel/10 border border-steel/20 p-8">
        <h2 className="font-serif text-3xl text-navy mb-4">Sampling Protocol</h2>
        <p className="font-sans text-lg text-textPrimary">
          Lowest available economy fare across all flights for a route/date, sampled daily at 10:00 IST.
        </p>
      </section>

      {/* Data Cleaning Rules */}
      <section className="bg-white border border-border p-8">
        <h2 className="font-serif text-3xl text-navy mb-6">Data Cleaning Rules</h2>
        <ul className="space-y-4 font-sans text-textPrimary list-disc pl-5">
          <li className="leading-relaxed">
            <strong className="text-navy">Outlier Flagging (Active):</strong> Outliers are flagged (outlier_flag=True) not deleted. They are kept in the raw dataset/API for auditability, and excluded only from aggregation math. For groups with fewer than 4 quotes, an absolute plausibility bound is applied instead of IQR: fares must be &gt;= ₹500, and &lt;= 10x the highest fare ever recorded for that route (or ₹200,000 ceiling if no history exists).
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Median Aggregation:</strong> Daily index values use median rather than mean to resist volatility.
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Economy-Only Scope:</strong> Current index excludes Business class fares from the core index; they are tracked separately.
          </li>
        </ul>
      </section>

      {/* Index Formula */}
      <section className="bg-white border border-border p-8">
        <h2 className="font-serif text-3xl text-navy mb-2">Index Formula</h2>
        <p className="font-sans text-xs text-textSecondary mb-6">
          Status: Active. The Laspeyres-style index computation engine is fully built and actively weights routes against a configuration file (DGCA_ROUTE_WEIGHTS). For this demo, the file is populated with estimated placeholder weights (e.g., DEL-BOM at 25%), not yet sourced from an official DGCA traffic report. In production, MoSPI would populate this config with exact passenger-volume figures from official monthly DGCA traffic reports to yield the verified index.
        </p>
        <div className="bg-[#1C2530] text-gray-200 font-mono text-sm p-6 overflow-x-auto rounded-sm">
          <pre>
{`Udaan Metrics_t = (Σ (P_it * W_i) / Σ (P_i0 * W_i)) * 100

Where: 
P_it = Current price at time t
P_i0 = Base period price
W_i  = DGCA-derived route weight for route i`}
          </pre>
        </div>
      </section>

      {/* Known Limitations */}
      <section className="bg-[#FFF8F0] border-l-4 border-l-saffron border-y border-r border-y-border border-r-border p-8 shadow-sm">
        <h2 className="font-serif text-3xl text-navy mb-6">Known Limitations</h2>
        <ul className="space-y-4 font-sans text-textPrimary list-disc pl-5">
          <li className="leading-relaxed">
            <strong className="text-navy">Carrier Scope:</strong> IndiGo, SpiceJet, Air India, and Akasa Air have dedicated, tested scrapers (4 of 5 planned carriers). Air India Express data appears incidentally when Air India's system routes to an Express-operated flight, has not been independently validated, and is explicitly excluded from the composite index math. These rows are retained in the raw dataset with an "Unvalidated" badge for transparency, but they do not affect the index value.
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Route Weights:</strong> The six active routes (DEL-BOM, DEL-BLR, BOM-BLR, DEL-CCU, BLR-HYD, MAA-DEL) are weighted using estimated placeholder values in DGCA_ROUTE_WEIGHTS, not yet sourced from an official DGCA traffic report. The weights sum to 0.90; the composite calculation automatically re-normalizes across whichever routes report data each day, so the effective sum is always treated as 1.0. In production, MoSPI would replace these with exact passenger-volume figures from official DGCA monthly traffic reports.
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Composite Index Coverage:</strong> On any day where a route reports zero valid quotes (all fares flagged as outliers, or scraper failure), the composite index automatically re-normalizes weights across the remaining reporting routes. Route coverage in the composite can therefore vary day to day.
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Rate Thresholds:</strong> IndiGo soft-blocks around 15 requests per session, mitigated via chunked batches with 30–45 second cooldown periods. SpiceJet has shown no throttling across 30 consecutive requests in testing. Air India and Akasa Air rate-limit thresholds have not yet been empirically measured.
          </li>
          <li className="leading-relaxed">
            <strong className="text-navy">Business vs Economy Fare Gap:</strong> This secondary metric is computed dynamically from real scraped data for the selected route. It displays "Insufficient data" when fewer than 2 business-class quotes exist for that route, rather than showing any placeholder number.
          </li>
        </ul>
      </section>

    </div>
  );
};

export default MethodologyTab;
