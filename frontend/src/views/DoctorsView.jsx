import { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  PawPrint, ClipboardList, CalendarDays, Users, Package,
  Bot, BarChart2, Layers, CalendarCog, Stethoscope, Plus, Receipt,
} from "lucide-react";
import PatientsTab from "../components/tabs/PatientsTab";
import VisitsTab from "../components/tabs/VisitsTab";
import CalendarTab from "../components/tabs/CalendarTab";
import InventoryTab from "../components/tabs/InventoryTab";
import AIAssistantTab from "../components/tabs/AIAssistantTab";
import WaitingRoomTab from "../components/tabs/WaitingRoomTab";
import ServiceCatalogTab from "../components/tabs/ServiceCatalogTab";
import OwnerDashboardTab from "../components/tabs/OwnerDashboardTab";
import SchedulerTab from "../components/tabs/SchedulerTab";
import InvoicesTab from "../components/tabs/InvoicesTab";
import LoginModal from "../components/LoginModal";
import StartVisitModal from "../components/modals/StartVisitModal";
import { authAPI, queueAPI, vetsAPI } from "../services/api";
import "../components/tabs/Tabs.css";
import "./DoctorsView.css";

const LANGUAGES = [
  { code: "pl", label: "Polski", flag: "🇵🇱" },
  { code: "en", label: "English", flag: "🇬🇧" },
];

const DoctorsView = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isAuthenticated, setIsAuthenticated] = useState(
    !!localStorage.getItem("access_token")
  );
  const [currentUser, setCurrentUser] = useState(null);
  const [currentUserId, setCurrentUserId] = useState(null);
  const [userRole, setUserRole] = useState(null);
  const [vets, setVets] = useState([]);
  const [selectedVetId, setSelectedVetId] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(
    !localStorage.getItem("access_token")
  );
  const [headerVisitActive, setHeaderVisitActive] = useState(false);
  const [headerVisitInitialPatient, setHeaderVisitInitialPatient] = useState(null);
  const [calledQueueEntry, setCalledQueueEntry] = useState(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  const rawTab = searchParams.get("tab");
  const activeTab =
    (rawTab === "active-visit" && !calledQueueEntry) ||
    (rawTab === "new-visit" && !headerVisitActive)
      ? "calendar"
      : rawTab || "calendar";

  const fetchCurrentUser = () => {
    authAPI.me().then((res) => {
      const { id, username, first_name, last_name, role } = res.data;
      if (role === "receptionist") {
        navigate("/receptionist", { replace: true });
        return;
      }
      const displayName =
        first_name && last_name ? `${first_name} ${last_name}` : username;
      setCurrentUser(displayName);
      setCurrentUserId(id);
      setUserRole(role);
    }).catch(() => {});
  };

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      fetchCurrentUser();
      vetsAPI.list().then((res) => setVets(res.data.results || res.data || [])).catch(() => {});
    }
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setCurrentUser(null);
      setShowLoginModal(true);
      setShowUserMenu(false);
    };
    window.addEventListener("auth:logout", handleUnauthorized);
    return () => window.removeEventListener("auth:logout", handleUnauthorized);
  }, []);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setShowUserMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setIsAuthenticated(false);
    setCurrentUser(null);
    setShowLoginModal(true);
    setShowUserMenu(false);
  };

  const handleTabChange = (tabId) => {
    setSearchParams({ tab: tabId });
  };

  const avatarInitials = currentUser
    ? currentUser.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
    : null;

  const currentLang = i18n.language?.slice(0, 2) || "pl";

  const staticTabs = [
    { id: "patients", label: t("tabs.patients"), icon: PawPrint },
    { id: "visits", label: t("tabs.visits"), icon: ClipboardList },
    { id: "calendar", label: t("tabs.calendar"), icon: CalendarDays },
    { id: "waiting-room", label: t("tabs.waitingRoom"), icon: Users },
    { id: "inventory", label: t("tabs.inventory"), icon: Package },
    { id: "ai-assistant", label: t("tabs.aiAssistant"), icon: Bot },
  ];

  const adminTabs = userRole === "admin" ? [
    { id: "owner-dashboard", label: t("tabs.ownerDashboard"), icon: BarChart2 },
    { id: "billing", label: t("tabs.billing"), icon: Receipt },
    { id: "service-catalog", label: t("tabs.serviceCatalog"), icon: Layers },
    { id: "scheduler", label: t("tabs.scheduler"), icon: CalendarCog },
  ] : [];

  const dynamicTabs = [
    ...(calledQueueEntry
      ? [{ id: "active-visit", label: calledQueueEntry.patient?.name || t("tabs.activeVisit"), icon: Stethoscope, dynamic: true }]
      : []),
    ...(headerVisitActive
      ? [{ id: "new-visit", label: t("tabs.newVisit"), icon: Plus, dynamic: true }]
      : []),
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "patients":
        return <PatientsTab userRole={userRole} />;
      case "visits":
        return <VisitsTab userRole={userRole} currentUserId={currentUserId} />;
      case "calendar":
        return (
          <CalendarTab
            vets={vets}
            vetId={selectedVetId}
            onVetChange={setSelectedVetId}
            currentUserId={currentUserId}
            userRole={userRole}
            onStartVisit={(appointment) => {
              setHeaderVisitInitialPatient(appointment?.patient || null);
              setHeaderVisitActive(true);
              setSearchParams({ tab: "new-visit" });
            }}
          />
        );
      case "waiting-room":
        return (
          <WaitingRoomTab
            userRole={userRole}
            hasActiveVisit={!!calledQueueEntry}
            onCallPatient={(entry) => {
              setCalledQueueEntry(entry);
              setSearchParams({ tab: "active-visit" });
            }}
          />
        );
      case "inventory":
        return <InventoryTab />;
      case "ai-assistant":
        return <AIAssistantTab />;
      case "billing":
        return <InvoicesTab />;
      case "service-catalog":
        return <ServiceCatalogTab />;
      case "owner-dashboard":
        return <OwnerDashboardTab />;
      case "scheduler":
        return <SchedulerTab />;
      default:
        return <PatientsTab />;
    }
  };

  const renderNavTab = (tab) => {
    const Icon = tab.icon;
    return (
      <button
        key={tab.id}
        className={`nav-tab${activeTab === tab.id ? " active" : ""}${tab.dynamic ? " dynamic" : ""}`}
        onClick={() => handleTabChange(tab.id)}
      >
        <Icon size={17} className="tab-icon" strokeWidth={1.75} />
        <span className="tab-label">{tab.label}</span>
      </button>
    );
  };

  return (
    <div className="doctors-view">
      {/* ── Sidebar ── */}
      <aside className="doctors-sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="sidebar-logo-mark">🐾</div>
          <div>
            <div className="sidebar-logo-text">Veto</div>
            <div className="sidebar-logo-sub">Clinic Manager</div>
          </div>
        </div>

        {/* Main navigation */}
        <nav className="doctors-nav">
          <div className="sidebar-section-label">{t("header.navSection")}</div>
          {staticTabs.map(renderNavTab)}

          {adminTabs.length > 0 && (
            <>
              <div className="sidebar-section-label">{t("header.adminSection")}</div>
              {adminTabs.map(renderNavTab)}
            </>
          )}

          {dynamicTabs.length > 0 && (
            <>
              <div className="sidebar-section-label">{t("header.activeSection")}</div>
              {dynamicTabs.map(renderNavTab)}
            </>
          )}
        </nav>

        {/* User footer */}
        <div className="sidebar-footer" ref={userMenuRef} style={{ position: "relative" }}>
          {showUserMenu && (
            <div className="sidebar-user-menu">
              {currentUser && (
                <div className="user-menu-header">
                  <div className="user-menu-name">{currentUser}</div>
                  {userRole && <div className="user-menu-role">{userRole}</div>}
                </div>
              )}
              <div className="user-menu-section">
                <div className="user-menu-lang">
                  {LANGUAGES.map((lang) => (
                    <button
                      key={lang.code}
                      className={`lang-btn${currentLang === lang.code ? " active" : ""}`}
                      onClick={() => {
                        i18n.changeLanguage(lang.code);
                        localStorage.setItem("veto-language", lang.code);
                      }}
                    >
                      <span>{lang.flag}</span>
                      <span>{lang.code.toUpperCase()}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="user-menu-divider" />
              <button className="user-menu-logout" onClick={handleLogout}>
                {t("header.logout")}
              </button>
            </div>
          )}

          <button
            className="sidebar-user-btn"
            onClick={() => setShowUserMenu((prev) => !prev)}
          >
            <div className="sidebar-avatar">{avatarInitials || "…"}</div>
            <span className="sidebar-user-name">{currentUser || "…"}</span>
          </button>
        </div>
      </aside>

      {/* ── Main body ── */}
      <div className="doctors-body">
        {/* Top bar */}
        <div className="doctors-topbar">
          <span className="topbar-title">
            {staticTabs.find((t) => t.id === activeTab)?.label ||
             adminTabs.find((t) => t.id === activeTab)?.label ||
             dynamicTabs.find((t) => t.id === activeTab)?.label ||
             ""}
          </span>
          <div className="topbar-actions">
            <button
              className="start-visit-btn"
              onClick={() => {
                setHeaderVisitActive(true);
                setSearchParams({ tab: "new-visit" });
              }}
            >
              ➕ {t("header.startVisit")}
            </button>
          </div>
        </div>

        {/* Content */}
        <main className="doctors-main">
          <div
            className="tab-content"
            style={["active-visit", "new-visit"].includes(activeTab) ? { display: "none" } : undefined}
          >
            {isAuthenticated && !["active-visit", "new-visit"].includes(activeTab) ? renderTabContent() : null}
          </div>

          {calledQueueEntry && (
            <div style={activeTab !== "active-visit" ? { display: "none" } : { overflowY: "auto", height: "100%" }}>
              <StartVisitModal
                standalone
                isOpen={true}
                initialPatient={calledQueueEntry.patient}
                initialChiefComplaint={calledQueueEntry.chief_complaint}
                onClose={async () => {
                  if (calledQueueEntry?.id) {
                    try { await queueAPI.requeue(calledQueueEntry.id); } catch (_) {}
                  }
                  setCalledQueueEntry(null);
                  setSearchParams({ tab: "waiting-room" });
                }}
                onSuccess={async () => {
                  if (calledQueueEntry?.id) {
                    try { await queueAPI.done(calledQueueEntry.id); } catch (_) {}
                  }
                  setCalledQueueEntry(null);
                  setSearchParams({ tab: "waiting-room" });
                }}
              />
            </div>
          )}

          {headerVisitActive && (
            <div style={activeTab !== "new-visit" ? { display: "none" } : { overflowY: "auto", height: "100%" }}>
              <StartVisitModal
                standalone
                isOpen={true}
                initialPatient={headerVisitInitialPatient}
                onClose={() => {
                  setHeaderVisitActive(false);
                  setHeaderVisitInitialPatient(null);
                  setSearchParams({ tab: "calendar" });
                }}
                onSuccess={() => {
                  setHeaderVisitActive(false);
                  setHeaderVisitInitialPatient(null);
                  setSearchParams({ tab: "visits" });
                }}
              />
            </div>
          )}
        </main>
      </div>

      {/* ── Mobile bottom nav ── */}
      <nav className="mobile-bottom-nav">
        {[...staticTabs, ...adminTabs, ...dynamicTabs].slice(0, 5).map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              className={`mobile-nav-btn${activeTab === tab.id ? " active" : ""}`}
              onClick={() => handleTabChange(tab.id)}
            >
              <Icon size={20} strokeWidth={1.75} />
              <span className="mobile-nav-label">{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <LoginModal
        isOpen={showLoginModal}
        isRequired={!isAuthenticated}
        onClose={() => isAuthenticated && setShowLoginModal(false)}
        onSuccess={() => {
          setIsAuthenticated(true);
          setShowLoginModal(false);
          setSearchParams({ tab: "calendar" });
          fetchCurrentUser();
        }}
      />
    </div>
  );
};

export default DoctorsView;
