import {
  Activity,
  ArrowRight,
  BellRing,
  Braces,
  CircleDashed,
  FlaskConical,
  Gauge,
  Settings2,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { Button } from "../components/ui/button.jsx";

const sectionDetails = {
  projects: {
    title: "Projects",
    description: "Connect API contracts and keep their quality work together.",
    message: "No API projects yet",
    detail: "Import an OpenAPI specification to create your first project. Project import is planned for Stage 2.",
    icon: Braces,
    canImport: true,
  },
  explorer: {
    title: "API Explorer",
    description: "Browse API operations and inspect contract details.",
    message: "An API definition is required",
    detail: "The explorer will be available after OpenAPI specifications can be imported.",
    icon: Braces,
    canImport: true,
  },
  testRuns: {
    title: "Test Runs",
    description: "Review execution history and investigate failed checks.",
    message: "No test executions",
    detail: "Generate cases, configure an approved target, and review real execution history in the Test Runs workspace.",
    icon: FlaskConical,
  },
  changes: {
    title: "Contract Changes",
    description: "Understand how API contract revisions affect consumers.",
    message: "No contract comparisons",
    detail: "Breaking-change detection will follow the OpenAPI import foundation.",
    icon: ShieldAlert,
  },
  performance: {
    title: "Performance",
    description: "Monitor response latency and reliability over time.",
    message: "No performance telemetry",
    detail: "No API traffic is monitored in Stage 1, so there are no response measurements to display.",
    icon: Gauge,
  },
  insights: {
    title: "AI Insights",
    description: "Surface actionable observations from API quality signals.",
    message: "Insights are not active",
    detail: "This Stage 2 foundation does not analyze API specifications or runtime data with AI.",
    icon: Sparkles,
  },
  alerts: {
    title: "Alerts",
    description: "Review reliability and contract notifications in one place.",
    message: "No alerts to show",
    detail: "Alerts will be generated when API monitoring and contract checks are implemented.",
    icon: BellRing,
  },
  settings: {
    title: "Settings",
    description: "Manage workspace preferences and service connections.",
    message: "Workspace settings are coming later",
    detail: "The current local development setup uses environment variables for backend configuration.",
    icon: Settings2,
  },
};

export default function PlaceholderPage({ section, onImport }) {
  const details = sectionDetails[section] ?? sectionDetails.projects;
  const Icon = details.icon ?? Activity;

  return (
    <div className="placeholder-page">
      <div className="page-heading-row">
        <div>
          <div className="page-breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{details.title}</strong></div>
          <h1>{details.title}</h1>
          <p className="page-description">{details.description}</p>
        </div>
        {details.canImport && <Button className="import-button" onClick={onImport}>Import API specification <ArrowRight size={15} /></Button>}
      </div>

      {section === "projects" && (
        <div className="empty-table-panel">
          <div className="table-toolbar">
            <div className="table-toolbar-title"><strong>All projects</strong><span>API specifications connected to this workspace</span></div>
            <span className="table-count">No projects</span>
          </div>
          <div className="table-scroll">
            <table className="data-table projects-table">
              <thead><tr><th>PROJECT</th><th>SPECIFICATION</th><th>LAST UPDATED</th><th>STATUS</th></tr></thead>
              <tbody><tr><td className="table-empty" colSpan="4"><span className="table-empty-icon"><Braces size={17} /></span><strong>No API projects yet</strong><span>Imported specifications will appear in this list.</span></td></tr></tbody>
            </table>
          </div>
        </div>
      )}

      {section !== "projects" && (
        <section className="module-empty-panel">
          <div className="module-empty-icon"><Icon size={20} strokeWidth={1.7} /></div>
          <p className="section-overline">STAGE 1 FOUNDATION</p>
          <h2>{details.message}</h2>
          <p>{details.detail}</p>
          {details.canImport && <Button variant="secondary" size="sm" onClick={onImport}>Import a specification <ArrowRight size={14} /></Button>}
          <span className="module-empty-mark"><CircleDashed size={94} strokeWidth={0.65} /></span>
        </section>
      )}
    </div>
  );
}