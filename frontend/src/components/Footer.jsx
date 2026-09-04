import React from 'react';

const Footer = () => {
  return (
    <footer className="border-t border-border bg-white mt-12 py-6 px-8 flex flex-col md:flex-row justify-between items-center gap-4 text-sm font-sans text-textSecondary text-center md:text-left">
      <div className="font-serif font-bold text-navy text-lg leading-none whitespace-nowrap">Udaan Metrics</div>
      <div className="flex flex-wrap justify-center gap-4 md:gap-6">
        <a href="#" className="hover:text-navy transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">GitHub Repository</a>
        <a href="#" className="hover:text-navy transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">Problem Statement 26056</a>
        <a href="#" className="hover:text-navy transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">Data Sources</a>
      </div>
      <div>&copy; 2026 Udaan Metrics &middot; SIH 26056 Prototype &middot; Submitted to MoSPI</div>
    </footer>
  );
};

export default Footer;
