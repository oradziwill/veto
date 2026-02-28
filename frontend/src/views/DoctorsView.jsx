import React, { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import PatientsTab from "../components/tabs/PatientsTab";
import VisitsTab from "../components/tabs/VisitsTab";
import CalendarTab from "../components/tabs/CalendarTab";
import InventoryTab from "../components/tabs/InventoryTab";
import AIAssistantTab from "../components/tabs/AIAssistantTab";
import LoginModal from "../components/LoginModal";
import StartVisitModal from "../components/modals/StartVisitModal";
import LanguageSwitcher from "../components/LanguageSwitcher";
import { authAPI } from "../services/api";
import "../components/tabs/Tabs.css";
import "./DoctorsView.css";

const DoctorsView = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") || "patients";
  const [isAuthenticated, setIsAuthenticated] = useState(
    !!localStorage.getItem("access_token")
  );
  const [currentUser, setCurrentUser] = useState(null);
  const [showLoginModal, setShowLoginModal] = useState(
    !localStorage.getItem("access_token")
  );
  const [showStartVisitModal, setShowStartVisitModal] = useState(false);

  // Listen for token expiry events dispatched by the API interceptor
  useEffect(() => {
    const handleUnauthorized = () => {
      setIsAuthenticated(false);
      setCurrentUser(null);
      setShowLoginModal(true);
    };
    window.addEventListener("auth:logout", handleUnauthorized);
    return () => window.removeEventListener("auth:logout", handleUnauthorized);
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setIsAuthenticated(false);
    setCurrentUser(null);
    setShowLoginModal(true);
  };

  const handleTabChange = (tabId) => {
    setSearchParams({ tab: tabId });
  };

  const tabs = [
    { id: "patients", label: t("tabs.patients"), icon: "🐾" },
    { id: "visits", label: t("tabs.visits"), icon: "📋" },
    { id: "calendar", label: t("tabs.calendar"), icon: "📅" },
    { id: "inventory", label: t("tabs.inventory"), icon: "📦" },
    { id: "ai-assistant", label: t("tabs.aiAssistant"), icon: "🤖" },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "patients":
        return <PatientsTab />;
      case "visits":
        return <VisitsTab />;
      case "calendar":
        return <CalendarTab />;
      case "inventory":
        return <InventoryTab />;
      case "ai-assistant":
        return <AIAssistantTab />;
      default:
        return <PatientsTab />;
    }
  };

  return (
    <div className="doctors-view">
      <header className="doctors-header">
        <div className="header-content">
          <h1 className="header-title">{t("header.title")}</h1>
          <div className="header-actions">
            <LanguageSwitcher />
            <button
              onClick={() => setShowStartVisitModal(true)}
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
            <div className="header-user">
              <span className="user-name">{currentUser || "—"}</span>
              <div className="user-avatar">
                {currentUser ? currentUser.slice(0, 2).toUpperCase() : "?"}
              </div>
              <button
                onClick={handleLogout}
                style={{
                  padding: "0.5rem 1rem",
                  fontSize: "0.875rem",
                  fontWeight: "600",
                  background: "transparent",
                  color: "white",
                  border: "1px solid rgba(255,255,255,0.6)",
                  borderRadius: "6px",
                  cursor: "pointer",
                }}
              >
                {t("header.logout")}
              </button>
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
          <div className="tab-content">{isAuthenticated ? renderTabContent() : null}</div>
        </main>
      </div>

      <LoginModal
        isOpen={showLoginModal}
        isRequired={!isAuthenticated}
        onClose={() => isAuthenticated && setShowLoginModal(false)}
        onSuccess={(username) => {
          setIsAuthenticated(true);
          setCurrentUser(username);
          setShowLoginModal(false);
        }}
      />

      <StartVisitModal
        isOpen={showStartVisitModal}
        onClose={() => setShowStartVisitModal(false)}
        onSuccess={() => {
          setShowStartVisitModal(false);
          // Refresh visits tab if it's active
          if (activeTab === "visits") {
            window.location.reload(); // Simple refresh for now
          }
        }}
      />
    </div>
  );
};

export default DoctorsView;
