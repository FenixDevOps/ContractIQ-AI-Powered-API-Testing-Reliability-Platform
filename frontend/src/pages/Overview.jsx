import { ArrowRight, ArrowUpRight, Check, CircleDot, FileUp, Layers3, Sparkles } from "lucide-react";

export default function Overview({ onImport }) {
  return (
    <div className="overview-page">
      <section className="welcome-row">
        <div>
          <p className="eyebrow"><span className="eyebrow-line" /> YOUR API RELIABILITY WORKSPACE</p>
          <h1>Good to have you here.</h1>
          <p className="welcome-copy">A clearer view of your APIs starts with a specification.</p>
        </div>
        <button className="primary-button" onClick={onImport} type="button">
          <FileUp size={16} aria-hidden="true" />
          Import API Specification
          <ArrowRight size={15} aria-hidden="true" />
        </button>
      </section>

      <section className="setup-section" aria-labelledby="setup-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">GETTING STARTED</p>
            <h2 id="setup-title">Workspace setup</h2>
          </div>
          <span className="setup-tag"><CircleDot size={13} /> In progress</span>
        </div>
        <div className="setup-panel">
          <div className="setup-track" aria-hidden="true">
            <span className="track-node completed"><Check size={12} /></span>
            <span className="track-line" />
            <span className="track-node current">02</span>
            <span className="track-line" />
            <span className="track-node">03</span>
          </div>
          <div className="setup-steps">
            <div className="setup-step is-done">
              <span>01</span><strong>Connect workspace</strong><small>Ready</small>
            </div>
            <div className="setup-step is-current">
              <span>02</span><strong>Import an API</strong><small>Next step</small>
            </div>
            <div className="setup-step">
              <span>03</span><strong>Explore your contract</strong><small>Coming later</small>
            </div>
          </div>
        </div>
      </section>

      <section className="empty-projects" aria-labelledby="empty-title">
        <div className="empty-copy">
          <span className="empty-icon"><Layers3 size={20} strokeWidth={1.7} /></span>
          <p className="eyebrow">API PROJECTS</p>
          <h2 id="empty-title">Your API space is ready.</h2>
          <p>No API specifications have been imported yet. Add one to start building your reliability workspace.</p>
          <button className="text-button" onClick={onImport} type="button">
            Import your first API <ArrowRight size={15} aria-hidden="true" />
          </button>
        </div>
        <div className="empty-visual" aria-hidden="true">
          <div className="visual-orbit orbit-outer" />
          <div className="visual-orbit orbit-inner" />
          <div className="visual-core"><Sparkles size={25} strokeWidth={1.4} /></div>
          <span className="visual-node node-top"><span /></span>
          <span className="visual-node node-right"><span /></span>
          <span className="visual-node node-bottom"><span /></span>
          <span className="visual-caption">SPECIFICATION<br />→ INSIGHT</span>
        </div>
      </section>

      <section className="trend-panel" aria-labelledby="trend-title">
        <div className="trend-heading">
          <div>
            <p className="eyebrow">OBSERVABILITY</p>
            <h2 id="trend-title">Reliability trend</h2>
          </div>
          <span className="trend-state"><span /> No telemetry</span>
        </div>
        <div className="trend-chart" role="img" aria-label="Empty reliability trend chart. No telemetry has been collected.">
          <div className="chart-empty-state">
            <span className="chart-empty-mark"><span /><span /><span /><span /></span>
            <strong>No response data yet</strong>
            <p>Monitoring will be available in a later stage.</p>
          </div>
        </div>
      </section>

      <section className="signal-row" aria-label="Workspace status">
        <div className="signal-item">
          <span className="signal-number">01</span>
          <div><strong>Connected foundation</strong><small>Frontend and backend are linked</small></div>
          <Check size={16} className="signal-check" aria-label="Complete" />
        </div>
        <div className="signal-divider" />
        <div className="signal-item muted-signal">
          <span className="signal-number">02</span>
          <div><strong>Reliability insights</strong><small>Available as the project grows</small></div>
          <ArrowUpRight size={15} className="signal-arrow" aria-hidden="true" />
        </div>
      </section>
    </div>
  );
}