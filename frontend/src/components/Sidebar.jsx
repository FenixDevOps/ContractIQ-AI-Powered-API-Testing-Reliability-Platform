import {
  Activity,
  BellRing,
  Blocks,
  Braces,
  ChartNoAxesCombined,
  CircleHelp,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Radio,
  UserRound,
  Settings2,
  ShieldAlert,
  Sparkles,
  X,
} from "lucide-react";
import { Button } from "./ui/button.jsx";
import { API_DOCS_URL } from "../services/api.js";

export const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard, group: "workspace" },
  { id: "projects", label: "Projects", icon: Blocks, group: "workspace" },
  { id: "explorer", label: "API Explorer", icon: Braces, group: "workspace" },
  { id: "testRuns", label: "Test Runs", icon: FlaskConical, group: "quality" },
  { id: "changes", label: "Breaking Changes", icon: ShieldAlert, group: "quality" },
  { id: "monitoring", label: "Monitoring", icon: Activity, group: "quality" },
  { id: "performance", label: "Performance", icon: ChartNoAxesCombined, group: "quality" },
  { id: "errors", label: "Errors", icon: ShieldAlert, group: "quality" },
  { id: "insights", label: "AI Insights", icon: Sparkles, group: "intelligence" },
  { id: "live", label: "Live Monitoring", icon: Radio, group: "intelligence" },
  { id: "alerts", label: "Alerts", icon: BellRing, group: "intelligence" },
  { id: "profile", label: "Profile", icon: UserRound, group: "system" },
  { id: "settings", label: "Settings", icon: Settings2, group: "system" },
];

const groups = [
  { id: "workspace", label: "WORKSPACE" },
  { id: "quality", label: "QUALITY" },
  { id: "intelligence", label: "INTELLIGENCE" },
  { id: "system", label: "SYSTEM" },
];

export default function Sidebar({ activeSection, onNavigate, isOpen, onClose, connectionState }) {
  return (
    <>
      {isOpen && <button className="mobile-scrim" type="button" aria-label="Close navigation" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? "sidebar-open" : ""}`} aria-label="Main navigation">
        <div className="sidebar-topline">
          <a className="brand" href="#overview" onClick={() => onNavigate("overview")}>
            <span className="brand-mark" aria-hidden="true"><Activity size={17} strokeWidth={2.2} /></span>
            <span>Contract<span className="brand-accent">IQ</span></span>
          </a>
          <Button className="mobile-close" variant="ghost" size="icon" aria-label="Close navigation" onClick={onClose}>
            <X size={17} />
          </Button>
        </div>

        <div className="sidebar-environment">
          <span className="environment-mark">L</span>
          <span className="environment-copy"><strong>Local workspace</strong><small>Development</small></span>
          <span className="environment-chevron" aria-hidden="true">⌄</span>
        </div>

        <nav className="sidebar-navigation" aria-label="Workspace sections">
          {groups.map((group) => (
            <div className="nav-group" key={group.id}>
              <p className="nav-group-label">{group.label}</p>
              {navigation.filter((item) => item.group === group.id).map(({ id, label, icon: Icon }) => (
                <button
                  className={`nav-item ${activeSection === id ? "is-active" : ""}`}
                  key={id}
                  type="button"
                  aria-current={activeSection === id ? "page" : undefined}
                  onClick={() => onNavigate(id)}
                >
                  <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="connection-note">
            <span className="connection-note-icon"><Gauge size={14} /></span>
            <span><strong>ContractIQ API</strong><small>Local connection</small></span>
            <span className={`connection-note-dot connection-note-${connectionState}`} />
          </div>
          <a className="help-link" href={API_DOCS_URL} target="_blank" rel="noreferrer">
            <CircleHelp size={15} /> API documentation <span>↗</span>
          </a>
          <div className="sidebar-version"><span>CONTRACTIQ</span><span>STAGE 6</span></div>
        </div>
      </aside>
    </>
  );
}