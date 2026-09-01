

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

export const getDailyIndex = async () => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/index/daily`);
      if (res.ok) return await res.json();
    } catch (e) {
      console.warn("API fetch failed", e);
    }
  }
  return null;
};

export const getRouteIndex = async (pair) => {
  if (API_BASE) {
    try {
      const res = await fetch(`${API_BASE}/index/route/${pair}`);
      if (res.ok) return await res.json();
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
