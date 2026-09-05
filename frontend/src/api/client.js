

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export const getDailyIndex = async () => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/index/latest`);
      if (res.ok) {
        const data = await res.json();
        // Map the new backend format to the legacy frontend format
        return {
          value: data.composite_fare_index,
          date: data.latest_date,
          status: "Live Official Data",
          carriers: ["IndiGo", "SpiceJet", "Air India", "Akasa Air"],
          routes_tracked: 6,
          days_live: data.total_days_collected || 0,
          advance_windows: 5,
          ota_premium_pct: 0.0, // Legacy fallback
          timestamp: data.latest_date + "T23:59:00+05:30"
        };
      }
    } catch (e) {
      console.warn("API fetch failed", e);
    }
  }
  return null;
};

export const getRouteIndex = async (pair) => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/index/history?route=${pair}`);
      if (res.ok) {
         const data = await res.json();
         if (!data.records) return { trend: [] };
         
         const base_val = data.records.length > 0 ? data.records[0][`fare_${pair}`] : 1;
         
         const trend = data.records.map(r => ({
             date: r.date,
             value: base_val ? ((r[`fare_${pair}`] / base_val) * 100).toFixed(1) : 100,
             isLive: true
         }));
         return { trend };
      }
    } catch (e) {
      console.warn("API fetch failed", e);
    }
  }
  return { trend: [] };
};

export const getRawFares = async () => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/fares/raw`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("API fetch failed", e);
    }
  }
  return [];
};

export const getHeatmap = async () => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/index/heatmap`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("API fetch failed", e);
    }
  }
  return [];
};
