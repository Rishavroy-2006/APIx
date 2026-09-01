import React, { useState, useEffect } from 'react';
import Header from './components/Header.jsx';
import Footer from './components/Footer.jsx';
import OverviewTab from './components/OverviewTab.jsx';
import LiveDataTab from './components/LiveDataTab.jsx';
import MethodologyTab from './components/MethodologyTab.jsx';
import AboutTab from './components/AboutTab.jsx';
import { getDailyIndex } from './api/client.js';

export default function App() {
  const [activeTab, setActiveTab] = useState('Overview');
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
    <div className="min-h-screen bg-bg flex flex-col">
      <Header 
        activeTab={activeTab} 
        setActiveTab={setActiveTab} 
        lastUpdated={indexData?.timestamp}
      />
      
      <main className="flex-grow flex flex-col">
        {activeTab === 'Overview' && <OverviewTab indexData={indexData} setActiveTab={setActiveTab} />}
        {activeTab === 'Live Data' && <LiveDataTab />}
        {activeTab === 'Methodology' && <MethodologyTab />}
        {activeTab === 'About' && <AboutTab />}
      </main>

      <Footer />
    </div>
  );
}
