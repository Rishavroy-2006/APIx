import React from 'react';

const Header = ({ activeTab, setActiveTab, lastUpdated }) => {
  const tabs = ['Overview', 'Citizen Portal', 'Gov Portal', 'Live Data', 'Methodology', 'About'];

  return (
    <header className="bg-navy text-white px-6 py-4 flex flex-col md:flex-row md:items-center justify-between shadow-sm sticky top-0 z-50 gap-4 md:gap-0">
      <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-12">
        <h1 className="font-serif text-2xl font-bold tracking-tight">APIx</h1>
        <nav className="flex gap-4 md:gap-8 overflow-x-auto pb-2 md:pb-0">
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`py-2 px-3 border-b-2 text-sm font-sans tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white ${
                activeTab === tab 
                  ? 'border-white font-medium text-white' 
                  : 'border-transparent text-gray-400 hover:text-gray-200'
              }`}
            >
              {tab}
            </button>
          ))}
        </nav>
      </div>
      <div className="text-xs font-sans text-gray-400">
        Data as of: {lastUpdated ? new Date(lastUpdated).toLocaleString() : 'Loading...'}
      </div>
    </header>
  );
};

export default Header;
