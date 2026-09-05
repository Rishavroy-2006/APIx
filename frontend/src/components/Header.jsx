import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { SkeletonText } from './common/SkeletonLoaders.jsx';

const Header = ({ lastUpdated }) => {
  const location = useLocation();
  const tabs = [
    { name: 'Overview', path: '/' },
    { name: 'Citizen Portal', path: '/citizen-portal' },
    { name: 'Gov Portal', path: '/gov-portal' },
    { name: 'Live Data', path: '/live-data' },
    { name: 'Methodology', path: '/methodology' },
    { name: 'About', path: '/about' },
  ];

  return (
    <header className="bg-navy text-white px-6 py-4 flex flex-col md:flex-row md:items-center justify-between shadow-sm sticky top-0 z-50 gap-4 md:gap-0">
      <div className="flex flex-col md:flex-row md:items-center gap-6 md:gap-12">
        <h1 className="font-serif text-2xl font-bold tracking-tight">Udaan Metrics</h1>
        <nav className="flex gap-4 md:gap-8 overflow-x-auto pb-2 md:pb-0">
          {tabs.map((tab) => {
            const isActive = location.pathname === tab.path;
            return (
              <Link
                key={tab.name}
                to={tab.path}
                className={`py-2 px-3 border-b-2 text-sm font-sans tracking-wide transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-white ${
                  isActive 
                    ? 'border-white font-medium text-white' 
                    : 'border-transparent text-gray-400 hover:text-gray-200'
                }`}
              >
                {tab.name}
              </Link>
            );
          })}
        </nav>
      </div>
      <div className="text-xs font-sans text-gray-400">
        Data as of: {lastUpdated ? new Date(lastUpdated).toLocaleString() : <SkeletonText className="inline-block h-3 w-32 ml-1 align-middle" />}
      </div>
    </header>
  );
};

export default Header;
