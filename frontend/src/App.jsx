import React, { useState, useEffect, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { SkeletonPage, SkeletonGovPortal, SkeletonCitizenPortal, SkeletonLiveData, SkeletonText } from './components/common/SkeletonLoaders.jsx';
import Header from './components/Header.jsx';
import Footer from './components/Footer.jsx';
import OverviewTab from './components/OverviewTab.jsx';
import { getDailyIndex } from './api/client.js';

// Lazy load heavy dashboard components
const LiveDataTab = React.lazy(() => import('./components/LiveDataTab.jsx'));
const MethodologyTab = React.lazy(() => import('./components/MethodologyTab.jsx'));
const AboutTab = React.lazy(() => import('./components/AboutTab.jsx'));
const GovernmentDashboard = React.lazy(() => import('./components/GovernmentDashboard.jsx'));
const CitizenDashboard = React.lazy(() => import('./components/CitizenDashboard.jsx'));

// Dynamic loading fallback
const TabLoader = () => {
  const location = useLocation();
  switch (location.pathname) {
    case '/gov-portal': return <SkeletonGovPortal />;
    case '/citizen-portal': return <SkeletonCitizenPortal />;
    case '/live-data': return <SkeletonLiveData />;
    case '/methodology':
    case '/about':
      return <div className="max-w-4xl mx-auto p-12"><SkeletonText lines={10} /></div>;
    default: return <SkeletonPage />;
  }
};

export default function App() {
  const [indexData, setIndexData] = useState(null);

  useEffect(() => {
    async function fetchGlobalData() {
      const data = await getDailyIndex();
      if (data) {
        setIndexData(data);
      }
    }
    fetchGlobalData();
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-bg flex flex-col">
        <Header 
          lastUpdated={indexData?.timestamp}
        />
        
        <main className="flex-grow flex flex-col">
          <Suspense fallback={<TabLoader />}>
            <Routes>
              <Route path="/" element={<OverviewTab indexData={indexData} />} />
              <Route path="/citizen-portal" element={<CitizenDashboard />} />
              <Route path="/gov-portal" element={<GovernmentDashboard />} />
              <Route path="/live-data" element={<LiveDataTab />} />
              <Route path="/methodology" element={<MethodologyTab />} />
              <Route path="/about" element={<AboutTab />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </main>

        <Footer />
      </div>
    </Router>
  );
}
