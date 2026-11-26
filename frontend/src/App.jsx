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
import ImportDialog from "./components/ImportDialog.jsx";
import { ChangesPage, ExplorerPage, ProjectsPage } from "./pages/Stage2Pages.jsx";
import TestingPage from "./pages/TestingPage.jsx";
import { API_DOCS_URL, fetchHealth, getProjects } from "./services/api.js";

export default function App() {
  const [activeSection, setActiveSection] = useState("overview");
  const [explorerProjectId, setExplorerProjectId] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [projectLoadError, setProjectLoadError] = useState("");
  const [connectionState, setConnectionState] = useState("loading");
  const [overlay, setOverlay] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const searchInputRef = useRef(null);
  const activePage = navigation.find((item) => item.id === activeSection) ?? navigation[0];

  const refreshProjects = useCallback(async (preferredId = "") => {
    const items = await getProjects();
    setProjects(items);
    setSelectedProjectId((current) => {
      if (preferredId && items.some((item) => item.id === preferredId)) return preferredId;
      return items.some((item) => item.id === current) ? current : items[0]?.id || "";
    });
    setProjectLoadError("");
  }, []);

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
    void refreshProjects().catch((error) => setProjectLoadError(error.message));
  }, [refreshProjects]);

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
                <span>{projects.find((item) => item.id === selectedProjectId)?.name || "No project selected"}</span>
                <ChevronDown size={14} />
              </Button>
              {isProjectMenuOpen && (
                <div className="popover project-popover" role="dialog" aria-label="Project selector">
                  <div className="popover-heading"><strong>Projects</strong><span>{projects.length} available</span></div>
                  {projectLoadError && <div className="stage-error" role="alert">{projectLoadError}</div>}
                  {projects.length === 0 ? <div className="popover-empty">
                    <span className="popover-empty-icon"><Command size={16} /></span>
                    <strong>No API projects yet</strong>
                    <span>Import a specification to create your first project.</span>
                  </div> : projects.map((project) => <button
                    className={`project-option ${project.id === selectedProjectId ? "is-selected" : ""}`}
                    key={project.id}
                    type="button"
                    onClick={() => {
                      setSelectedProjectId(project.id);
                      setExplorerProjectId(project.id);
                      setIsProjectMenuOpen(false);
                      navigate("explorer");
                    }}
                  >
                    <span>{project.name}</span><small>{project.specification_count} specifications</small>
                  </button>)}
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
                  <a href={API_DOCS_URL} target="_blank" rel="noreferrer"><UserRound size={15} /> API documentation</a>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="page-content">
          {activeSection === "overview" ? (
            <Overview connectionState={connectionState} onImport={() => setOverlay("import")} onNavigate={navigate} />
          ) : activeSection === "projects" ? (
            <ProjectsPage onImport={() => setOverlay("import")} onOpenExplorer={(projectId) => { setSelectedProjectId(projectId); setExplorerProjectId(projectId); navigate("explorer"); }} />
          ) : activeSection === "explorer" ? (
            <ExplorerPage onImport={() => setOverlay("import")} initialProjectId={explorerProjectId} />
          ) : activeSection === "changes" ? (
            <ChangesPage />
          ) : activeSection === "testRuns" ? (
            <TestingPage />
          ) : (
            <PlaceholderPage section={activeSection} onImport={() => setOverlay("import")} />
          )}
        </div>
        <footer className="main-footer">
          <span>ContractIQ <i /> Stage 4 compatibility analysis</span>
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
        <ImportDialog
          onClose={() => setOverlay(null)}
          onImported={(result) => {
            setExplorerProjectId(result.project_id);
            setSelectedProjectId(result.project_id);
            void refreshProjects(result.project_id).catch((error) => setProjectLoadError(error.message));
            setActiveSection("explorer");
          }}
        />
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