import {
  Activity,
  ArrowUpRight,
  Blocks,
  Gauge,
  LayoutDashboard,
  Settings2,
  ShieldAlert,
} from "lucide-react";

const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "projects", label: "API Projects", icon: Blocks },
  { id: "testing", label: "API Testing", icon: Activity },
  { id: "changes", label: "Breaking Changes", icon: ShieldAlert },
  { id: "performance", label: "Performance Monitoring", icon: Gauge },
];

export default function Sidebar({ activeSection, onNavigate }) {
  return (
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={() => onNavigate("overview")}>
        <span className="brand-mark" aria-hidden="true">C</span>
        <span className="brand-name">Contract<span>IQ</span></span>
      </a>

      <div className="workspace-switcher">
        <span className="workspace-avatar">D</span>
        <span className="workspace-copy">
          <strong>Developer workspace</strong>
          <small>Local environment</small>
        </span>
        <span className="workspace-caret" aria-hidden="true">⌄</span>
      </div>

      <p className="nav-label">WORKSPACE</p>
      <nav className="primary-nav" aria-label="Workspace navigation">
        {navigation.map(({ id, label, icon: Icon }) => (
          <button
            className={`nav-item ${activeSection === id ? "is-active" : ""}`}
            key={id}
            onClick={() => onNavigate(id)}
            type="button"
            aria-current={activeSection === id ? "page" : undefined}
          >
            <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />
      <div className="sidebar-note">
        <span className="note-icon"><Activity size={15} /></span>
        <div>
          <strong>Stage 1 foundation</strong>
          <p>API workspace is ready to connect.</p>
        </div>
      </div>
      <button
        className={`nav-item settings-link ${activeSection === "settings" ? "is-active" : ""}`}
        onClick={() => onNavigate("settings")}
        type="button"
        aria-current={activeSection === "settings" ? "page" : undefined}
      >
        <Settings2 size={17} strokeWidth={1.8} aria-hidden="true" />
        <span>Settings</span>
      </button>
      <a className="sidebar-footer" href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">
        API documentation <ArrowUpRight size={13} aria-hidden="true" />
      </a>
    </aside>
  );
}