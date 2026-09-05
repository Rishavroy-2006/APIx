import React, { useState, useEffect } from 'react';
import { SkeletonChart } from './common/SkeletonLoaders.jsx';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import { getRouteIndex, getRawFares, getHeatmap } from '../api/client.js';

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white border border-border p-3 text-sm font-sans shadow-sm">
        <p className="font-semibold text-navy mb-1">{label}</p>
        <p className="text-textPrimary">Index: <span className="font-mono">{payload[0].value}</span></p>
        <p className="text-xs text-textSecondary mt-1">
          {data.isLive ? 'Live scraped data' : 'Placeholder (pending)'}
        </p>
      </div>
    );
  }
  return null;
};

const LiveDataTab = () => {
  const [route, setRoute] = useState('DEL-BOM');
  const [carrier, setCarrier] = useState('All');
  const [rawFares, setRawFares] = useState([]);
  const [trendData, setTrendData] = useState([]);
  const [heatmapData, setHeatmapData] = useState([]);
  
  const CARRIER_CONFIG = {
    live: ["IndiGo", "SpiceJet", "Air India", "Akasa Air"],
    incidental: ["Air India Express"],
    phase2: []
  };
  
  const carriers = ['All', ...new Set(rawFares.map(f => f.carrier_name))].filter(Boolean);
  const uniqueRoutes = [...new Set(rawFares.map(f => `${f.origin}-${f.destination}`))].filter(Boolean);
  if (uniqueRoutes.length === 0) uniqueRoutes.push('DEL-BOM');

  useEffect(() => {
    async function loadData() {
      const indexRes = await getRouteIndex(route);
      if (indexRes && indexRes.trend) setTrendData(indexRes.trend);
      
      const faresRes = await getRawFares();
      if (faresRes) setRawFares(faresRes);
      
      const heatRes = await getHeatmap();
      if (heatRes) setHeatmapData(heatRes);
    }
    loadData();
  }, [route]);

  // Derived calculations
  const filteredFares = carrier === 'All' 
    ? rawFares 
    : rawFares.filter(f => f.carrier_name === carrier);
    
  const routeFares = filteredFares.filter(f => `${f.origin}-${f.destination}` === route);

  const liveCount = CARRIER_CONFIG.live.length;
  const totalCarriers = liveCount + CARRIER_CONFIG.incidental.length + CARRIER_CONFIG.phase2.length;

  const leadTimeMap = {};
  routeFares.forEach(f => {
    const w = `T+${f.advance_purchase_days}`;
    if (!leadTimeMap[w]) leadTimeMap[w] = { sum: 0, count: 0 };
    leadTimeMap[w].sum += f.total_fare;
    leadTimeMap[w].count += 1;
  });
  
  const leadTimeData = Object.keys(leadTimeMap)
    .sort((a,b) => parseInt(a.slice(2)) - parseInt(b.slice(2)))
    .map(w => ({
      window: w,
      value: Math.round(leadTimeMap[w].sum / leadTimeMap[w].count)
    }));
  const maxLeadTimeVal = Math.max(...leadTimeData.map(d => d.value));

  // Find latest timestamp
  const latestTimestamp = rawFares.length > 0 ? rawFares[0].scraped_at : 'Loading...';

  const parseDate = (dStr) => new Date(dStr).getTime();
  const chartData = trendData.map((d, i) => {
    return {
      ...d,
      time: parseDate(d.date),
      liveValue: d.isLive ? Number(d.value) : null,
    };
  });
  const chartTicks = chartData.map(d => d.time);
  
  let sampleFares = [];
  const firstOutlier = routeFares.find(f => f.status === 'parse_error' || f.outlier_flag === true || f.outlier_flag === 'True');
  const firstSoldOut = routeFares.find(f => f.status === 'sold_out');
  
  if (firstOutlier) sampleFares.push(firstOutlier);
  if (firstSoldOut) sampleFares.push(firstSoldOut);
  
  const activeFares = routeFares.filter(f => f.status === 'ok' && !f.outlier_flag);
  const carrierMap = {};
  activeFares.forEach(f => {
    if (!carrierMap[f.carrier_name]) carrierMap[f.carrier_name] = {};
    if (!carrierMap[f.carrier_name][f.advance_purchase_days]) carrierMap[f.carrier_name][f.advance_purchase_days] = [];
    carrierMap[f.carrier_name][f.advance_purchase_days].push(f);
  });
  
  const cList = Object.keys(carrierMap);
  const wList = [1, 7, 15, 30, 45];
  let roundNum = 0;
  let added = true;
  
  while(sampleFares.length < 8 && added) {
    added = false;
    for (let c of cList) {
        if (sampleFares.length >= 8) break;
        let w = wList[roundNum % wList.length];
        
        if (carrierMap[c][w] && carrierMap[c][w].length > 0) {
             sampleFares.push(carrierMap[c][w].shift());
             added = true;
        } else {
             const availW = Object.keys(carrierMap[c]).filter(kw => carrierMap[c][kw].length > 0);
             if (availW.length > 0) {
                 sampleFares.push(carrierMap[c][availW[0]].shift());
                 added = true;
             }
        }
    }
    roundNum++;
  }
  
  sampleFares.sort((a, b) => new Date(b.scraped_at).getTime() - new Date(a.scraped_at).getTime());

  // Business vs Economy multiplier — computed dynamically from real route data.
  // Only uses non-outlier 'ok' rows. If < 2 business quotes, shows "Insufficient data".
  const validFares = routeFares.filter(f => f.status === 'ok' && !(f.outlier_flag === true || f.outlier_flag === 'True'));
  const bizFares = validFares.filter(f => (f.fare_class || '').toLowerCase() === 'business' && f.total_fare != null && !Number.isNaN(Number(f.total_fare)));
  const ecoFares = validFares.filter(f => (f.fare_class || '').toLowerCase() === 'economy' && f.total_fare != null && !Number.isNaN(Number(f.total_fare)));
  let bizEcoMultiplier = null;
  if (bizFares.length >= 2 && ecoFares.length >= 1) {
    const meanBiz = bizFares.reduce((s, f) => s + Number(f.total_fare), 0) / bizFares.length;
    const meanEco = ecoFares.reduce((s, f) => s + Number(f.total_fare), 0) / ecoFares.length;
    if (meanEco > 0) bizEcoMultiplier = (meanBiz / meanEco).toFixed(1);
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-8 animate-fade-in">
      
      {/* Control Bar */}
      <div className="flex justify-between items-center bg-white border border-border p-4">
        <div className="flex items-center gap-2 font-sans text-sm">
          <span className="text-textSecondary">Route:</span>
          <select 
            value={route} 
            onChange={e => setRoute(e.target.value)}
            className="border-none bg-bg py-2 px-3 focus:ring-1 focus:ring-navy outline-none"
          >
            {uniqueRoutes.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2 font-sans text-sm">
          <span className="text-textSecondary">Carrier:</span>
          <select 
            value={carrier} 
            onChange={e => setCarrier(e.target.value)}
            className="border-none bg-bg py-2 px-3 focus:ring-1 focus:ring-navy outline-none"
          >
            {carriers.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* Rollout Status Strip */}
      <div className="bg-bg border border-border p-4 flex flex-col gap-3 text-sm font-sans">
        <div className="font-bold text-navy flex flex-col md:flex-row md:items-center gap-4">
          <span>Carrier Rollout: 4/5 Live</span>
          <div className="flex flex-wrap gap-2 font-normal">
            {CARRIER_CONFIG.live.map(c => (
              <span key={c} className="bg-green/10 text-green px-2 py-1 text-xs border border-green/20">{c}</span>
            ))}
            {CARRIER_CONFIG.incidental.map(c => (
              <span key={c} className="bg-orange-100 text-orange-700 px-2 py-1 text-xs border border-orange-200 cursor-help" title="Captured incidentally via the Air India scraper's operating-carrier detection — not yet independently verified or covered by a dedicated scraper.">{c} — Unvalidated</span>
            ))}
            {CARRIER_CONFIG.phase2.map(c => (
              <span key={c} className="bg-gray-200 text-textSecondary px-2 py-1 text-xs">{c} — Phase 2</span>
            ))}
          </div>
        </div>
        <div className="text-xs text-textSecondary leading-relaxed">
          IndiGo, SpiceJet, Air India, and Akasa Air have dedicated, tested scrapers. Air India Express data appears incidentally when Air India's system routes to an Express-operated flight, and has not been independently validated — treat these rows as directionally real but unverified until a dedicated scraper is built.
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Line Chart */}
        <div className="lg:col-span-2 bg-white border border-border p-6">
          <h3 className="font-serif text-xl text-navy mb-1">30-Day Route-Specific Price Trend — {route}</h3>
          <p className="text-xs text-textSecondary font-sans mb-6">Calculation: Simple Median (Unweighted Route Trend)</p>
          
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#D9DEE5" />
                <XAxis 
                  dataKey="time" 
                  type="number" 
                  domain={['dataMin', 'dataMax']}
                  ticks={chartTicks}
                  tickFormatter={(time) => {
                    const d = new Date(time);
                    return `${d.getMonth()+1}/${d.getDate()}`;
                  }} 
                  tick={{fontSize: 12, fill: '#5B6472'}} 
                  tickMargin={10} 
                  axisLine={false} 
                  tickLine={false} 
                />
                <YAxis width={80} tick={{fontSize: 12, fill: '#5B6472'}} axisLine={false} tickLine={false} domain={['dataMin - 5', 'dataMax + 5']} />
                <RechartsTooltip content={<CustomTooltip />} />
                {/* Live Line */}
                <Line type="monotone" dataKey="liveValue" stroke="#0B2C4D" strokeWidth={2} dot={{ fill: '#0B2C4D', strokeWidth: 2, r: 4 }} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex justify-center mt-6 text-xs font-sans text-textSecondary italic">
            Trend chart will grow more meaningful as daily collection continues. Currently showing all {chartData.length} real data points collected to date.
          </div>
        </div>

        {/* Bar Chart */}
        <div className="bg-white border border-border p-6">
          <h3 className="font-serif text-xl text-navy mb-6">Lead-Time Elasticity</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={leadTimeData} margin={{ top: 20, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#D9DEE5" />
                <XAxis dataKey="window" tick={{fontSize: 12, fill: '#5B6472'}} axisLine={false} tickLine={false} />
                <YAxis width={80} tickFormatter={(val) => `₹${val.toLocaleString()}`} tick={{fontSize: 12, fill: '#5B6472', fontFamily: 'sans-serif'}} axisLine={false} tickLine={false} />
                <Bar dataKey="value" radius={[2, 2, 0, 0]}>
                  {leadTimeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.value === maxLeadTimeVal ? '#E98A15' : '#1B4B75'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Sector-Wise Heatmap */}
      <div className="bg-white border border-border p-6">
        <h3 className="font-serif text-xl text-navy mb-4">Sector-Wise DoD Change (Heatmap)</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {heatmapData.map(h => (
            <div key={h.route} className={`p-4 border flex flex-col items-center justify-center rounded-sm transition-colors ${h.pct_change === 0 ? 'bg-gray-100 border-gray-200 text-textSecondary' : h.pct_change > 0 ? 'bg-red/10 border-red/20 text-red' : 'bg-green/10 border-green/20 text-green'}`}>
              <span className="font-sans text-xs font-semibold mb-1 text-navy">{h.route}</span>
              <span className="font-mono text-lg font-bold">
                {h.pct_change === 0 ? 'Collecting data' : `${h.pct_change > 0 ? '+' : ''}${h.pct_change}%`}
              </span>
              <span className="font-sans text-[10px] opacity-70">₹{h.current_fare.toLocaleString()}</span>
            </div>
          ))}
          {heatmapData.length === 0 && <SkeletonChart height="h-64" title={false} />}
        </div>
      </div>

      {/* Table Section */}
      <div className="bg-white border border-border overflow-hidden">
        <div className="p-4 bg-bg border-b border-border flex justify-between items-center">
          <h3 className="font-serif text-lg text-navy">Representative Fare Sample</h3>
          <p className="text-xs text-textSecondary font-sans">
            Diversified across carriers and advance-purchase windows &middot; Full dataset available via API
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-sans text-sm">
            <thead className="bg-white border-b border-border text-textSecondary">
              <tr>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs">Window</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs">Carrier</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs">Flight No.</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs">Fare Class</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-right">Base Fare</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-right">Taxes</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-right">Total</th>
                <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sampleFares.map((fare, i) => {
                const isOutlier = fare.status === 'parse_error' || fare.outlier_flag === true || fare.outlier_flag === 'True';
                const isIncidental = CARRIER_CONFIG.incidental.includes(fare.carrier_name);
                
                return (
                  <tr key={i} className="hover:bg-bg transition-colors">
                    <td className="px-6 py-4 font-mono tabular-nums">T+{fare.advance_purchase_days}</td>
                    <td className="px-6 py-4 text-textPrimary">{fare.carrier_name}</td>
                    <td className="px-6 py-4 text-textSecondary">{fare.flight_num}</td>
                    <td className="px-6 py-4">
                      <span className={`px-3 py-1 text-xs rounded-full ${
                        (fare.fare_class || 'Unknown').toLowerCase() === 'business' 
                          ? 'bg-navy text-white' 
                          : 'bg-steel text-white'
                      }`}>
                        {(fare.fare_class || 'Unknown').charAt(0).toUpperCase() + (fare.fare_class || 'Unknown').slice(1)}
                      </span>
                    </td>
                    <td className={`px-6 py-4 font-mono tabular-nums text-right ${isOutlier ? 'line-through text-red' : ''}`}>
                      {fare.base_fare != null && fare.base_fare !== '' && !Number.isNaN(Number(fare.base_fare)) ? `₹${Number(fare.base_fare).toLocaleString()}` : '—'}
                    </td>
                    <td className={`px-6 py-4 font-mono tabular-nums text-right ${isOutlier ? 'line-through text-red' : ''}`}>
                      {fare.taxes_and_fees != null && fare.taxes_and_fees !== '' && !Number.isNaN(Number(fare.taxes_and_fees)) ? `₹${Number(fare.taxes_and_fees).toLocaleString()}` : '—'}
                    </td>
                    <td className={`px-6 py-4 font-mono tabular-nums text-right font-medium ${isOutlier ? 'line-through text-red' : 'text-navy'}`}>
                      {fare.total_fare != null && fare.total_fare !== '' && !Number.isNaN(Number(fare.total_fare)) ? `₹${Number(fare.total_fare).toLocaleString()}` : '—'}
                    </td>
                    <td className="px-6 py-4 flex flex-col md:flex-row items-start md:items-center gap-2">
                      {fare.status === 'ok' && <span className="text-green text-xs font-semibold uppercase">Active</span>}
                      {fare.status === 'sold_out' && <span className="text-gray-500 text-xs font-semibold uppercase">Sold Out</span>}
                      {fare.status === 'parse_error' && <span className="text-orange-500 text-xs font-semibold uppercase">Error</span>}
                      {isOutlier && <span className="text-red text-xs font-semibold uppercase">Outlier — Flagged</span>}
                      {isIncidental && <span className="bg-orange-100 border border-orange-200 text-orange-700 text-[10px] px-2 py-0.5 uppercase tracking-wider cursor-help" title="Captured incidentally via the Air India scraper's operating-carrier detection — not yet independently verified or covered by a dedicated scraper.">Unvalidated</span>}
                    </td>
                  </tr>
                );
              })}
              {sampleFares.length === 0 && (
                <tr>
                  <td colSpan="8" className="px-6 py-8 text-center text-textSecondary">No data available for selected filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bottom Cards & Status */}
      <div className="flex flex-col md:flex-row justify-between items-end gap-6">
        <div className="border border-border bg-white p-6 min-w-[250px]">
          <p className="text-xs text-textSecondary font-sans mb-1">Secondary metric — excluded from index</p>
          <h4 className="font-serif text-lg text-navy mb-4">Business vs Economy Fare Gap</h4>
          {bizEcoMultiplier !== null ? (
            <div className="flex items-baseline gap-3">
              <span className="font-serif text-5xl text-navy">{bizEcoMultiplier}x</span>
              <span className="font-sans text-sm text-textSecondary">Multiplier ({bizFares.length} business / {ecoFares.length} economy quotes)</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="font-sans text-sm text-textSecondary italic">Insufficient data</span>
              <span className="font-sans text-xs text-textSecondary">(requires ≥ 2 business quotes for {route})</span>
            </div>
          )}
        </div>
      </div>

      <div className="text-xs font-sans text-textSecondary border-t border-border pt-4">
        Last updated: {latestTimestamp ? new Date(latestTimestamp).toLocaleString() : '...'} &middot; Route: {route}
      </div>
      
    </div>
  );
};

export default LiveDataTab;
