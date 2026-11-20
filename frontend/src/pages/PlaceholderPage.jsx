import { ArrowUpRight, CircleDashed } from "lucide-react";

const sectionDetails = {
  projects: {
    eyebrow: "WORKSPACE / API PROJECTS",
    title: "API Projects",
    description: "Your connected API specifications will live here. Import is planned for Stage 2.",
  },
  testing: {
    eyebrow: "WORKSPACE / API TESTING",
    title: "API Testing",
    description: "Generated and executed API checks are not part of Stage 1.",
  },
  changes: {
    eyebrow: "WORKSPACE / BREAKING CHANGES",
    title: "Breaking Changes",
    description: "Contract comparison will be introduced after the OpenAPI import foundation.",
  },
  performance: {
    eyebrow: "WORKSPACE / PERFORMANCE MONITORING",
    title: "Performance Monitoring",
    description: "No monitoring data is collected in Stage 1. This space is reserved for a later stage.",
  },
  settings: {
    eyebrow: "WORKSPACE / SETTINGS",
    title: "Settings",
    description: "Workspace preferences and integrations will be configurable in a future stage.",
  },
};

export default function PlaceholderPage({ section }) {
  const details = sectionDetails[section];

  return (
    <section className="placeholder-page">
      <p className="eyebrow"><span className="eyebrow-line" /> {details.eyebrow}</p>
      <h1>{details.title}</h1>
      <p className="placeholder-intro">{details.description}</p>
      <div className="placeholder-state">
        <span className="placeholder-icon"><CircleDashed size={23} strokeWidth={1.5} /></span>
        <div>
          <p className="eyebrow">STAGE 1 FOUNDATION</p>
          <h2>This area is not active yet</h2>
          <p>ContractIQ is being built in stages. This view will become available when its foundation is implemented.</p>
        </div>
        <span className="later-label">Planned <ArrowUpRight size={13} /></span>
      </div>
    </section>
  );
}