import React from 'react';

const AboutTab = () => {
  return (
    <div className="max-w-3xl mx-auto px-6 py-16 space-y-16 animate-fade-in text-center">
      
      <section>
        <h1 className="font-serif text-4xl md:text-5xl text-navy font-bold mb-4">Udaan Metrics — Real-time Airfare Price Index</h1>
        <p className="font-sans text-textSecondary text-lg max-w-2xl mx-auto leading-relaxed">
          SIH Problem Statement 26056 &middot; MoSPI &middot; Data Informatics & Innovation Division &middot; Theme: Smart Automation
        </p>
      </section>

      <section>
        <h2 className="font-serif text-2xl text-navy mb-6">Project Team</h2>
        <div className="bg-white border border-border py-4 px-8 inline-block shadow-sm">
          <p className="font-sans text-textSecondary italic">Team names to be finalized</p>
        </div>
      </section>

      <section>
        <h2 className="font-serif text-2xl text-navy mb-6">Technical Infrastructure</h2>
        <div className="flex flex-wrap justify-center gap-3">
          {['Python', 'Playwright', 'FastAPI', 'React', 'Recharts', 'Tailwind CSS'].map(tag => (
            <span key={tag} className="font-sans text-sm bg-steel text-white px-4 py-1.5 rounded-full shadow-sm">
              {tag}
            </span>
          ))}
        </div>
      </section>

      <section>
        <h2 className="font-serif text-2xl text-navy mb-6">Resources</h2>
        <div className="flex flex-col items-center gap-4">
          <a href="#" className="font-sans text-navy hover:text-steel underline underline-offset-4 decoration-border hover:decoration-steel transition-colors">GitHub Repository</a>
          <a href="#" className="font-sans text-navy hover:text-steel underline underline-offset-4 decoration-border hover:decoration-steel transition-colors">Standalone Pipeline Demo (illustrative simulation)</a>
          <a href="#" className="font-sans text-navy hover:text-steel underline underline-offset-4 decoration-border hover:decoration-steel transition-colors">Scraper Source Code</a>
        </div>
      </section>

      <section className="text-left bg-white border border-border p-8 shadow-sm">
        <h2 className="font-serif text-2xl text-navy mb-2">API Access</h2>
        <p className="font-sans text-sm text-textSecondary mb-6">REST endpoints for RBI/MoSPI system integration (see Methodology for details).</p>
        <div className="space-y-3 font-mono text-sm text-navy bg-bg p-4 border border-border">
          <div>/index/daily</div>
          <div>/index/route/{'{pair}'}</div>
          <div>/fares/raw</div>
        </div>
      </section>

    </div>
  );
};

export default AboutTab;
