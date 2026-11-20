import { useCallback, useEffect, useState } from "react";
import { Bell, ChevronRight, Command } from "lucide-react";
import ConnectionStatus from "./components/ConnectionStatus.jsx";
import Sidebar from "./components/Sidebar.jsx";
import Overview from "./pages/Overview.jsx";
import PlaceholderPage from "./pages/PlaceholderPage.jsx";
import { fetchHealth } from "./services/api.js";

const sectionTitles = {
  overview: "Overview",
  projects: "API Projects",
  testing: "API Testing",
  changes: "Breaking Changes",
  performance: "Performance Monitoring",
  settings: "Settings",
};

export default function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [connectionState, setConnectionState] = useState("loading");
  const [isImportNoticeOpen, setIsImportNoticeOpen] = useState(false);

  const checkConnection = useCallback(async () => {
    setConnectionState("loading");
    try {
      await fetchHealth();
      setConnectionState("connected");
    } catch {
      setConnectionState("disconnected");
    }
  }, []);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    function closeOnEscape(event) {
      if (event.key === "Escape") setIsImportNoticeOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  return (
    <div className="app-shell">
      <Sidebar activeSection={activeSection} onNavigate={setActiveSection} />
      <main className="main-area">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span><ChevronRight size={14} /><strong>{sectionTitles[activeSection]}</strong>
          </div>
          <div className="topbar-actions">
            <ConnectionStatus state={connectionState} onRetry={checkConnection} compact />
            <span className="topbar-divider" />
            <button className="icon-button notification-button" type="button" aria-label="Notifications">
              <Bell size={17} strokeWidth={1.8} />
              <span className="notification-dot" />
            </button>
            <span className="user-avatar" aria-label="Developer profile">D</span>
          </div>
        </header>

        <div className="page-content">
          {activeSection === "overview" ? (
            <Overview onImport={() => setIsImportNoticeOpen(true)} />
          ) : (
            <PlaceholderPage section={activeSection} />
          )}
        </div>
        <footer className="main-footer">
          <span><Command size={13} /> CONTRACTIQ <span className="footer-separator">/</span> STAGE 1</span>
          <span>Local development workspace</span>
        </footer>
      </main>

      {isImportNoticeOpen && (
        <div className="modal-backdrop" onMouseDown={(event) => {
          if (event.target === event.currentTarget) setIsImportNoticeOpen(false);
        }}>
          <section className="coming-soon-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
            <span className="modal-icon"><Command size={21} /></span>
            <p className="eyebrow">NEXT UP · STAGE 2</p>
            <h2 id="modal-title">OpenAPI import is coming next.</h2>
            <p>The Stage 1 foundation is in place. The import engine will let you bring an API specification into this workspace.</p>
            <button className="primary-button modal-close" onClick={() => setIsImportNoticeOpen(false)} type="button">
              Got it
            </button>
          </section>
        </div>
      )}
    </div>
  );
}