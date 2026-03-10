import React, { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PatientsTab from "../components/tabs/PatientsTab";
import VisitsTab from "../components/tabs/VisitsTab";
import CalendarTab from "../components/tabs/CalendarTab";
import InventoryTab from "../components/tabs/InventoryTab";
import AIAssistantTab from "../components/tabs/AIAssistantTab";
import WaitingRoomTab from "../components/tabs/WaitingRoomTab";
import ServiceCatalogTab from "../components/tabs/ServiceCatalogTab";
import LoginModal from "../components/LoginModal";
import StartVisitModal from "../components/modals/StartVisitModal";
import { authAPI, queueAPI } from "../services/api";
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
  const [userRole, setUserRole] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(
    !localStorage.getItem("access_token")
  );
  const [headerVisitActive, setHeaderVisitActive] = useState(false);
  const [headerVisitInitialPatient, setHeaderVisitInitialPatient] = useState(null);
  const [calledQueueEntry, setCalledQueueEntry] = useState(null);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const userMenuRef = useRef(null);

  const rawTab = searchParams.get("tab");
  // Fall back to calendar if a visit tab is in the URL but the visit state is gone (stale URL)
  const activeTab =
    (rawTab === "active-visit" && !calledQueueEntry) ||
    (rawTab === "new-visit" && !headerVisitActive)
      ? "calendar"
      : rawTab || "calendar";

  // Fetch user info from /api/me/ so it persists across page reloads
  const fetchCurrentUser = () => {
    authAPI.me().then((res) => {
      const { username, first_name, last_name, role } = res.data;
      if (role === "receptionist") {
        navigate("/receptionist", { replace: true });
        return;
      }
      const displayName =
        first_name && last_name ? `${first_name} ${last_name}` : username;
      setCurrentUser(displayName);
      setUserRole(role);
    }).catch(() => {
      // 401 handled by interceptor (dispatches auth:logout)
    });
  };

  useEffect(() => {
    if (localStorage.getItem("access_token")) {
      fetchCurrentUser();
    }
  }, []);

  // Listen for token expiry events dispatched by the API interceptor
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

  // Close user menu when clicking outside
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

  const tabs = [
    { id: "patients", label: t("tabs.patients"), icon: "🐾" },
    { id: "visits", label: t("tabs.visits"), icon: "📋" },
    { id: "calendar", label: t("tabs.calendar"), icon: "📅" },
    { id: "waiting-room", label: t("tabs.waitingRoom"), icon: "🏥" },
    { id: "inventory", label: t("tabs.inventory"), icon: "📦" },
    { id: "ai-assistant", label: t("tabs.aiAssistant"), icon: "🤖" },
    ...(userRole === "admin"
      ? [{ id: "service-catalog", label: t("tabs.serviceCatalog"), icon: "🗂️" }]
      : []),
    ...(calledQueueEntry
      ? [{ id: "active-visit", label: calledQueueEntry.patient?.name || t("tabs.activeVisit"), icon: "🩺" }]
      : []),
    ...(headerVisitActive
      ? [{ id: "new-visit", label: t("tabs.newVisit"), icon: "➕" }]
      : []),
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "patients":
        return <PatientsTab />;
      case "visits":
        return <VisitsTab />;
      case "calendar":
        return (
          <CalendarTab
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
      case "service-catalog":
        return <ServiceCatalogTab />;
      default:
        return <PatientsTab />;
    }
  };

  const currentLang = i18n.language?.slice(0, 2) || "pl";

  return (
    <div className="doctors-view">
      <header className="doctors-header">
        <div className="header-content">
          <h1 className="header-title">{t("header.title")}</h1>
          <div className="header-actions">
            <button
              onClick={() => {
                setHeaderVisitActive(true);
                setSearchParams({ tab: "new-visit" });
              }}
              className="start-visit-btn"
              style={{
                padding: "0.75rem 1.5rem",
                fontSize: "1rem",
                fontWeight: "600",
                background: "white",
                color: "#2f855a",
                border: "2px solid white",
                borderRadius: "8px",
                cursor: "pointer",
                boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
              }}
            >
              {t("header.startVisit")}
            </button>

            {/* User avatar + settings dropdown */}
            <div
              ref={userMenuRef}
              className="header-user"
              style={{ position: "relative" }}
            >
              <button
                onClick={() => setShowUserMenu((prev) => !prev)}
                className="user-avatar"
                title={currentUser || ""}
                style={{
                  cursor: "pointer",
                  border: "2px solid rgba(255,255,255,0.7)",
                  background: "rgba(255,255,255,0.15)",
                  color: "white",
                  width: "40px",
                  height: "40px",
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: "700",
                  fontSize: "0.9rem",
                  letterSpacing: "0.05em",
                }}
              >
                {avatarInitials || "…"}
              </button>

              {showUserMenu && (
                <div
                  style={{
                    position: "absolute",
                    top: "calc(100% + 10px)",
                    right: 0,
                    background: "white",
                    borderRadius: "12px",
                    boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
                    border: "1px solid #e2e8f0",
                    minWidth: "220px",
                    zIndex: 1000,
                    overflow: "hidden",
                  }}
                >
                  {/* User info */}
                  {currentUser && (
                    <div
                      style={{
                        padding: "1rem",
                        borderBottom: "1px solid #e2e8f0",
                        background: "#f7fafc",
                      }}
                    >
                      <div
                        style={{
                          fontWeight: "600",
                          color: "#2d3748",
                          fontSize: "0.95rem",
                        }}
                      >
                        {currentUser}
                      </div>
                    </div>
                  )}

                  {/* Language */}
                  <div
                    style={{
                      padding: "0.75rem 1rem",
                      borderBottom: "1px solid #e2e8f0",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.75rem",
                        fontWeight: "600",
                        color: "#718096",
                        textTransform: "uppercase",
                        letterSpacing: "0.05em",
                        marginBottom: "0.5rem",
                      }}
                    >
                      {t("header.language")}
                    </div>
                    <div style={{ display: "flex", gap: "0.5rem" }}>
                      {LANGUAGES.map((lang) => {
                        const active = currentLang === lang.code;
                        return (
                          <button
                            key={lang.code}
                            onClick={() => {
                              i18n.changeLanguage(lang.code);
                              localStorage.setItem("veto-language", lang.code);
                            }}
                            style={{
                              flex: 1,
                              padding: "0.4rem 0.5rem",
                              border: `2px solid ${active ? "#48bb78" : "#e2e8f0"}`,
                              borderRadius: "8px",
                              background: active ? "#f0fff4" : "white",
                              cursor: "pointer",
                              fontSize: "0.85rem",
                              fontWeight: active ? "600" : "400",
                              color: active ? "#276749" : "#4a5568",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: "0.3rem",
                            }}
                          >
                            <span>{lang.flag}</span>
                            <span>{lang.code.toUpperCase()}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Logout */}
                  <button
                    onClick={handleLogout}
                    style={{
                      width: "100%",
                      padding: "0.75rem 1rem",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      color: "#e53e3e",
                      fontWeight: "600",
                      textAlign: "left",
                      fontSize: "0.9rem",
                    }}
                  >
                    {t("header.logout")}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="doctors-content">
        <nav className="doctors-nav">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => handleTabChange(tab.id)}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </nav>

        <main className="doctors-main">
          {/* Regular tab content — hidden when on a visit tab */}
          <div
            className="tab-content"
            style={["active-visit", "new-visit"].includes(activeTab) ? { display: "none" } : undefined}
          >
            {isAuthenticated && !["active-visit", "new-visit"].includes(activeTab) ? renderTabContent() : null}
          </div>

          {/* Queue visit form — always mounted while calledQueueEntry is set */}
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

          {/* Header "Rozpocznij wizytę" form — always mounted while headerVisitActive */}
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
