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
import MonitoringPage from "./pages/MonitoringPage.jsx";
import AuthPage from "./pages/AuthPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import {
  acceptProjectInvite,
  API_DOCS_URL,
  fetchHealth,
  getProjects,
  logout as endSession,
  refreshAuthSession,
  setAccessToken,
} from "./services/api.js";

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
  const [authStatus, setAuthStatus] = useState("loading");
  const [authMode, setAuthMode] = useState("login");
  const [currentUser, setCurrentUser] = useState(null);
  const [resetToken, setResetToken] = useState("");
  const [verificationToken, setVerificationToken] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [workspaceNotice, setWorkspaceNotice] = useState("");
  const searchInputRef = useRef(null);
  const acceptedInviteTokenRef = useRef("");
  const activePage = navigation.find((item) => item.id === activeSection) ?? navigation[0];

  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const token = params.get("reset_token");
    const verification = params.get("verify_token");
    const invite = params.get("invite_token");
    if (token) {
      setResetToken(token);
      setAuthMode("reset");
    }
    if (verification) {
      setVerificationToken(verification);
      setAuthMode("verify");
    }
    if (invite) setInviteToken(invite);
    if (token || verification || invite) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }

    let active = true;
    if (verification) {
      setAuthStatus("signed-out");
      return () => { active = false; };
    }
    refreshAuthSession()
      .then((session) => {
        if (!active) return;
        if (session?.user) {
          setCurrentUser(session.user);
          setAuthStatus("signed-in");
        } else {
          setAuthStatus("signed-out");
        }
      })
      .catch(() => {
        if (active) setAuthStatus("signed-out");
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    function handleAuthExpiry() {
      setAccessToken("");
      setCurrentUser(null);
      setProjects([]);
      setSelectedProjectId("");
      setActiveSection("overview");
      setAuthStatus("signed-out");
      setAuthMode("login");
    }
    window.addEventListener("contractiq:auth-expired", handleAuthExpiry);
    return () => window.removeEventListener("contractiq:auth-expired", handleAuthExpiry);
  }, []);

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
    if (authStatus !== "signed-in") {
      setProjects([]);
      setSelectedProjectId("");
      return;
    }
    void refreshProjects().catch((error) => setProjectLoadError(error.message));
  }, [authStatus, refreshProjects]);

  useEffect(() => {
    if (authStatus !== "signed-in" || !inviteToken) return undefined;
    if (acceptedInviteTokenRef.current === inviteToken) return undefined;
    acceptedInviteTokenRef.current = inviteToken;
    let active = true;
    acceptProjectInvite(inviteToken)
      .then((project) => {
        if (!active) return;
        setWorkspaceNotice(`Joined ${project.name}.`);
        setInviteToken("");
        void refreshProjects(project.id).catch((error) => setProjectLoadError(error.message));
      })
      .catch((error) => {
        if (active) {
          setWorkspaceNotice("");
          setProjectLoadError(`Invitation could not be accepted: ${error.message}`);
          setInviteToken("");
        }
      });
    return () => { active = false; };
  }, [authStatus, inviteToken, refreshProjects]);

  useEffect(() => {
    if (!workspaceNotice) return undefined;
    const timer = window.setTimeout(() => setWorkspaceNotice(""), 5000);
    return () => window.clearTimeout(timer);
  }, [workspaceNotice]);

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

  function handleAuthenticated(session) {
    setAccessToken(session.access_token);
    setCurrentUser(session.user);
    setAuthStatus("signed-in");
    setAuthMode("login");
    setResetToken("");
    setVerificationToken("");
    setProjectLoadError("");
  }

  async function handleLogout() {
    try {
      await endSession();
    } catch (error) {
      setProjectLoadError(error.message);
    } finally {
      setAccessToken("");
      setCurrentUser(null);
      setProjects([]);
      setSelectedProjectId("");
      setActiveSection("overview");
      setAuthStatus("signed-out");
      setAuthMode("login");
      setIsProfileOpen(false);
    }
  }

  function handlePasswordChanged() {
    setAccessToken("");
    setCurrentUser(null);
    setProjects([]);
    setSelectedProjectId("");
    setActiveSection("overview");
    setAuthStatus("signed-out");
    setAuthMode("login");
  }

  if (authStatus === "loading") {
    return <main className="auth-page"><div className="auth-loading" role="status">Restoring your secure session…</div></main>;
  }
  if (authStatus !== "signed-in") {
    return (
      <AuthPage
        mode={authMode}
        resetToken={resetToken}
        verificationToken={verificationToken}
        onModeChange={(mode) => {
          setAuthMode(mode);
          if (mode !== "reset") setResetToken("");
          if (mode !== "verify") setVerificationToken("");
        }}
        onAuthenticated={handleAuthenticated}
      />
    );
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
                <span className="profile-avatar">{currentUser?.full_name?.[0]?.toUpperCase() || "U"}</span><ChevronDown size={13} />
              </Button>
              {isProfileOpen && (
                <div className="popover profile-popover" role="menu" aria-label="Profile menu">
                  <div className="profile-summary"><span className="profile-avatar">{currentUser?.full_name?.[0]?.toUpperCase() || "U"}</span><span><strong>{currentUser?.full_name}</strong><small>{currentUser?.email}</small></span></div>
                  <button type="button" role="menuitem" onClick={() => navigate("profile")}><UserRound size={15} /> Profile</button>
                  <button type="button" role="menuitem" onClick={() => navigate("settings")}><Settings2 size={15} /> Settings</button>
                  <a href={API_DOCS_URL} target="_blank" rel="noreferrer"><Command size={15} /> API documentation</a>
                  <button type="button" role="menuitem" onClick={handleLogout}>Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>

        <div className="page-content">
          {activeSection === "overview" ? (
            <Overview connectionState={connectionState} onImport={() => setOverlay("import")} onNavigate={navigate} />
          ) : activeSection === "projects" ? (
            <ProjectsPage
              onImport={() => setOverlay("import")}
              onOpenExplorer={(projectId) => { setSelectedProjectId(projectId); setExplorerProjectId(projectId); navigate("explorer"); }}
              onProjectsChanged={(preferredId) => void refreshProjects(preferredId).catch((error) => setProjectLoadError(error.message))}
            />
          ) : activeSection === "explorer" ? (
            <ExplorerPage onImport={() => setOverlay("import")} initialProjectId={explorerProjectId} />
          ) : activeSection === "changes" ? (
            <ChangesPage />
          ) : activeSection === "testRuns" ? (
            <TestingPage />
          ) : activeSection === "profile" ? (
            <ProfilePage
              user={currentUser}
              onProfileUpdated={setCurrentUser}
              onPasswordChanged={handlePasswordChanged}
            />
          ) : ["monitoring", "performance", "errors", "insights", "live", "alerts"].includes(activeSection) ? (
            <MonitoringPage section={activeSection} projectId={selectedProjectId} />
          ) : (
            <PlaceholderPage section={activeSection} onImport={() => setOverlay("import")} />
          )}
          {workspaceNotice && <div className="workspace-notice" role="status">{workspaceNotice}</div>}
          {projectLoadError && <div className="stage-error" role="alert">{projectLoadError}</div>}
        </div>
        <footer className="main-footer">
          <span>ContractIQ <i /> API quality workspace</span>
          <span>{currentUser?.email}</span>
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