import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  Command,
  Menu,
  Search,
  Settings2,
  UserRound,
  X,
} from "lucide-react";
import ConnectionStatus from "./components/ConnectionStatus.jsx";
import Sidebar, { navigation } from "./components/Sidebar.jsx";
import { Button } from "./components/ui/button.jsx";
import Overview from "./pages/Overview.jsx";
import PlaceholderPage from "./pages/PlaceholderPage.jsx";
import { fetchHealth } from "./services/api.js";

export default function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [connectionState, setConnectionState] = useState("loading");
  const [overlay, setOverlay] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const searchInputRef = useRef(null);
  const activePage = navigation.find((item) => item.id === activeSection) ?? navigation[0];

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
    function onKeyDown(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchQuery("");
        setOverlay("command");
      }
      if (event.key === "Escape") {
        setOverlay(null);
        setIsProjectMenuOpen(false);
        setIsNotificationOpen(false);
        setIsProfileOpen(false);
        setIsMobileNavOpen(false);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (overlay === "command") searchInputRef.current?.focus();
  }, [overlay]);

  function navigate(section) {
    setActiveSection(section);
    setIsMobileNavOpen(false);
    setIsProjectMenuOpen(false);
    setIsNotificationOpen(false);
    setIsProfileOpen(false);
    setOverlay(null);
  }

  function openCommand() {
    setSearchQuery("");
    setOverlay("command");
  }

  return (
    <div className="app-shell">
      <Sidebar
        activeSection={activeSection}
        onNavigate={navigate}
        isOpen={isMobileNavOpen}
        onClose={() => setIsMobileNavOpen(false)}
        connectionState={connectionState}
      />
      <main className="main-area">
        <header className="topbar">
          <div className="topbar-leading">
            <Button className="mobile-menu-button" variant="ghost" size="icon" aria-label="Open navigation" onClick={() => setIsMobileNavOpen(true)}>
              <Menu size={18} />
            </Button>
            <div className="breadcrumb" aria-label="Breadcrumb">
              <span>Workspace</span><ChevronRight size={14} aria-hidden="true" /><strong>{activePage.label}</strong>
            </div>
          </div>
          <div className="topbar-actions">
            <div className="menu-anchor project-anchor">
              <Button
                className="project-selector"
                variant="ghost"
                aria-expanded={isProjectMenuOpen}
                onClick={() => {
                  setIsProjectMenuOpen((open) => !open);
                  setIsNotificationOpen(false);
                  setIsProfileOpen(false);
                }}
              >
                <span className="project-selector-mark"><Command size={13} /></span>
                <span>No project selected</span>
                <ChevronDown size={14} />
              </Button>
              {isProjectMenuOpen && (
                <div className="popover project-popover" role="dialog" aria-label="Project selector">
                  <div className="popover-heading"><strong>Projects</strong><span>0 available</span></div>
                  <div className="popover-empty">
                    <span className="popover-empty-icon"><Command size={16} /></span>
                    <strong>No API projects yet</strong>
                    <span>Import a specification to create your first project.</span>
                  </div>
                  <Button className="popover-action" variant="secondary" size="sm" onClick={() => { setIsProjectMenuOpen(false); setOverlay("import"); }}>
                    Import API specification
                  </Button>
                </div>
              )}
            </div>

            <Button className="search-trigger" variant="outline" aria-label="Open search" onClick={openCommand}>
              <Search size={15} /><span>Search anything</span><kbd><Command size={11} /> K</kbd>
            </Button>
            <span className="topbar-divider" />
            <ConnectionStatus state={connectionState} onRetry={checkConnection} compact />

            <div className="menu-anchor">
              <Button
                className="top-icon-button"
                variant="ghost"
                size="icon"
                aria-label="Notifications"
                aria-expanded={isNotificationOpen}
                onClick={() => {
                  setIsNotificationOpen((open) => !open);
                  setIsProjectMenuOpen(false);
                  setIsProfileOpen(false);
                }}
              >
                <Bell size={17} />
              </Button>
              {isNotificationOpen && (
                <div className="popover notification-popover" role="dialog" aria-label="Notifications">
                  <div className="popover-heading"><strong>Notifications</strong><span className="quiet-badge">All caught up</span></div>
                  <div className="notification-empty">
                    <Check size={17} />
                    <span>No alerts or changes to show.</span>
                    <small>Notifications will appear here when an API is connected.</small>
                  </div>
                </div>
              )}
            </div>

            <div className="menu-anchor">
              <Button
                className="profile-button"
                variant="ghost"
                aria-label="Open profile menu"
                aria-expanded={isProfileOpen}
                onClick={() => {
                  setIsProfileOpen((open) => !open);
                  setIsProjectMenuOpen(false);
                  setIsNotificationOpen(false);
                }}
              >
                <span className="profile-avatar">D</span><ChevronDown size={13} />
              </Button>
              {isProfileOpen && (
                <div className="popover profile-popover" role="menu" aria-label="Profile menu">
                  <div className="profile-summary"><span className="profile-avatar">D</span><span><strong>Developer</strong><small>Local workspace</small></span></div>
                  <button type="button" role="menuitem" onClick={() => navigate("settings")}><Settings2 size={15} /> Settings</button>
                  <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer"><UserRound size={15} /> API documentation</a>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="page-content">
          {activeSection === "overview" ? (
            <Overview connectionState={connectionState} onImport={() => setOverlay("import")} onNavigate={navigate} />
          ) : (
            <PlaceholderPage section={activeSection} onImport={() => setOverlay("import")} />
          )}
        </div>
        <footer className="main-footer">
          <span>ContractIQ <i /> Stage 1 foundation</span>
          <span>Local development environment</span>
        </footer>
      </main>

      {overlay === "command" && (
        <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOverlay(null); }}>
          <section className="command-dialog" role="dialog" aria-modal="true" aria-labelledby="command-title">
            <h2 className="sr-only" id="command-title">Search and navigate</h2>
            <div className="command-search-row">
              <Search size={17} aria-hidden="true" />
              <input ref={searchInputRef} type="search" value={searchQuery} placeholder="Search pages and actions..." onChange={(event) => setSearchQuery(event.target.value)} />
              <Button variant="ghost" size="icon" aria-label="Close search" onClick={() => setOverlay(null)}><X size={16} /></Button>
            </div>
            <CommandResults query={searchQuery} onNavigate={navigate} onImport={() => setOverlay("import")} />
            <div className="command-hint"><span><kbd>Tab</kbd> to navigate</span><span><kbd>esc</kbd> to close</span></div>
          </section>
        </div>
      )}

      {overlay === "import" && (
        <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setOverlay(null); }}>
          <section className="import-dialog" role="dialog" aria-modal="true" aria-labelledby="import-title">
            <div className="dialog-icon"><Command size={18} /></div>
            <p className="dialog-kicker">PLANNED · STAGE 2</p>
            <h2 id="import-title">OpenAPI import is next.</h2>
            <p>The workspace is connected to its backend. The OpenAPI import engine is the next planned step; file upload is not available yet.</p>
            <Button className="dialog-dismiss" onClick={() => setOverlay(null)}>Understood</Button>
          </section>
        </div>
      )}
    </div>
  );
}

function CommandResults({ query, onNavigate, onImport }) {
  const normalizedQuery = query.trim().toLowerCase();
  const matches = navigation.filter((item) => item.label.toLowerCase().includes(normalizedQuery));
  const showImport = "import api specification".includes(normalizedQuery) || "import".includes(normalizedQuery);

  return (
    <div className="command-results">
      <p className="command-section-label">PAGES</p>
      {matches.length === 0 && !showImport ? <p className="command-no-results">No matching pages or actions.</p> : (
        matches.map(({ id, label, icon: Icon }) => (
          <button type="button" className="command-result" key={id} onClick={() => onNavigate(id)}>
            <Icon size={16} /><span>{label}</span><ChevronRight size={14} />
          </button>
        ))
      )}
      {showImport && <button type="button" className="command-result" onClick={onImport}><Command size={16} /><span>Import API specification</span><span className="result-stage">Stage 2</span></button>}
    </div>
  );
}