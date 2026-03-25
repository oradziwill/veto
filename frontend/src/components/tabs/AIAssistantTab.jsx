import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import "./Tabs.css";

const AIAssistantTab = () => {
  const { t, i18n } = useTranslation();
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: "assistant",
      content: t("aiAssistant.greeting"),
    },
  ]);

  // Update greeting when language changes
  useEffect(() => {
    setMessages((prev) =>
      prev.map((m, i) =>
        i === 0 && m.type === "assistant"
          ? { ...m, content: t("aiAssistant.greeting") }
          : m
      )
    );
  }, [i18n.language]);
  const [inputValue, setInputValue] = useState("");

  const handleSend = () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: messages.length + 1,
      type: "user",
      content: inputValue,
    };

    setMessages([...messages, userMessage]);
    setInputValue("");

    // Simulate AI response
    setTimeout(() => {
      const aiMessage = {
        id: messages.length + 2,
        type: "assistant",
        content:
          "I understand your question. This is a placeholder response. In the full implementation, I would analyze your query and provide relevant veterinary insights.",
      };
      setMessages((prev) => [...prev, aiMessage]);
    }, 1000);
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="tab-container">
      <div className="tab-header">
        <h2>{t("aiAssistant.title")}</h2>
        <div className="ai-info">
          <span className="ai-status">{t("aiAssistant.online")}</span>
        </div>
      </div>

      <div className="tab-content-wrapper ai-chat-wrapper">
        <div className="ai-chat">
          <div className="chat-messages">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`chat-message ${
                  message.type === "user" ? "user-message" : "assistant-message"
                }`}
              >
                <div className="message-avatar">
                  {message.type === "user" ? "👤" : "🤖"}
                </div>
                <div className="message-content">{message.content}</div>
              </div>
            ))}
          </div>

          <div className="chat-input-container">
            <textarea
              className="chat-input"
              placeholder={t("aiAssistant.placeholder")}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              rows={3}
            />
            <button className="btn-primary send-button" onClick={handleSend}>
              {t("aiAssistant.send")}
            </button>
          </div>
        </div>

        <div className="ai-suggestions">
          <h3>{t("aiAssistant.quickSuggestions")}</h3>
          <div className="suggestion-chips">
            <button className="suggestion-chip">{t("aiAssistant.diagnosisHelp")}</button>
            <button className="suggestion-chip">{t("aiAssistant.drugInteractions")}</button>
            <button className="suggestion-chip">{t("aiAssistant.treatmentOptions")}</button>
            <button className="suggestion-chip">{t("aiAssistant.dosageCalculator")}</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIAssistantTab;
