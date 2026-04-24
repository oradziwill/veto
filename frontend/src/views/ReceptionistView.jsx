import { useState, useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  CalendarDays, Users, PawPrint, ClipboardList, Receipt, Inbox, Bot,
} from "lucide-react";
import PatientsTab from "../components/tabs/PatientsTab";
import VisitsTab from "../components/tabs/VisitsTab";
import CalendarTab from "../components/tabs/CalendarTab";
import WaitingRoomTab from "../components/tabs/WaitingRoomTab";
import BillingTab from "../components/tabs/BillingTab";
import InboxTab from "../components/tabs/InboxTab";
import AssistantTab from "../components/tabs/AssistantTab";
import LoginModal from "../components/LoginModal";
import { authAPI, vetsAPI } from "../services/api";
import "../components/tabs/Tabs.css";
import "./DoctorsView.css";

const LANGUAGES = [
  { code: "pl", label: "Polski", flag: "🇵🇱" },
  { code: "en", label: "English", flag: "🇬🇧" },
];

const ReceptionistView = () => {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "calendar";

  const [isAuthenticated, setIsAuthenticated] = useState(
    !!localStorage.getItem("access_token")
  );
  const [currentUser, setCurrentUser] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(
    !localStorage.getItem("access_token")
  );
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [vets, setVets] = useState([]);
  const [selectedVetId, setSelectedVetId] = useState(null);
  const userMenuRef = useRef(null);

  const fetchCurrentUser = () => {
    authAPI.me().then((res) => {
      const { username, first_name, last_name, role } = res.data;
      if (role === "doctor" || role === "admin") {
        navigate("/doctors", { replace: true });
        return;
      }
      const displayName =
        first_name && last_name ? `${first_name} ${last_name}` : username;
      setCurrentUser(displayName);
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

  const handleTabChange = (tabId) => setSearchParams({ tab: tabId });

  const avatarInitials = currentUser
    ? currentUser.split(" ").map((w) => w[0]).join("").toUpperCase().slice(0, 2)
    : null;

  const currentLang = i18n.language?.slice(0, 2) || "pl";

  const tabs = [
    { id: "calendar",     label: t("tabs.calendar"),     icon: CalendarDays },
    { id: "waiting-room", label: t("tabs.waitingRoom"),  icon: Users },
    { id: "inbox",        label: t("tabs.inbox"),        icon: Inbox },
    { id: "patients",     label: t("tabs.patients"),     icon: PawPrint },
    { id: "visits",       label: t("tabs.visits"),       icon: ClipboardList },
    { id: "billing",      label: t("tabs.billing"),      icon: Receipt },
    { id: "assistant",    label: t("tabs.assistant"),    icon: Bot },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "calendar":
        return (
          <CalendarTab
            vets={vets}
            vetId={selectedVetId}
            onVetChange={setSelectedVetId}
            userRole="receptionist"
          />
        );
      case "waiting-room":
        return <WaitingRoomTab userRole="receptionist" />;
      case "inbox":
        return <InboxTab userRole="receptionist" />;
      case "patients":
        return <PatientsTab userRole="receptionist" />;
      case "visits":
        return <VisitsTab />;
      case "billing":
        return <BillingTab />;
      case "assistant":
        return <AssistantTab />;
      default:
        return (
          <CalendarTab
            vets={vets}
            vetId={selectedVetId}
            onVetChange={setSelectedVetId}
            userRole="receptionist"
          />
        );
    }
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
            <div className="sidebar-logo-sub">Reception</div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="doctors-nav">
          <div className="sidebar-section-label">{t("header.navSection")}</div>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                className={`nav-tab${activeTab === tab.id ? " active" : ""}`}
                onClick={() => handleTabChange(tab.id)}
              >
                <Icon size={17} className="tab-icon" strokeWidth={1.75} />
                <span className="tab-label">{tab.label}</span>
              </button>
            );
          })}
        </nav>

        {/* User footer */}
        <div className="sidebar-footer" ref={userMenuRef} style={{ position: "relative" }}>
          {showUserMenu && (
            <div className="sidebar-user-menu">
              {currentUser && (
                <div className="user-menu-header">
                  <div className="user-menu-name">{currentUser}</div>
                  <div className="user-menu-role">receptionist</div>
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
            {tabs.find((tab) => tab.id === activeTab)?.label || ""}
          </span>
        </div>

        {/* Content */}
        <main className="doctors-main">
          <div className="tab-content">
            {isAuthenticated ? renderTabContent() : null}
          </div>
        </main>
      </div>

      {/* ── Mobile bottom nav ── */}
      <nav className="mobile-bottom-nav">
        {tabs.map((tab) => {
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

export default ReceptionistView;
