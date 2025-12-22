import React, { useState } from "react";
import "./Tabs.css";

const AIAssistantTab = () => {
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: "assistant",
      content:
        "Hello! I'm your AI assistant. How can I help you today? I can assist with diagnosis suggestions, treatment recommendations, drug interactions, and general veterinary questions.",
    },
  ]);
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
        <h2>AI Assistant</h2>
        <div className="ai-info">
          <span className="ai-status">🟢 Online</span>
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
              placeholder="Ask me anything about veterinary care, diagnoses, treatments..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              rows={3}
            />
            <button className="btn-primary send-button" onClick={handleSend}>
              Send
            </button>
          </div>
        </div>

        <div className="ai-suggestions">
          <h3>Quick Suggestions</h3>
          <div className="suggestion-chips">
            <button className="suggestion-chip">Diagnosis help</button>
            <button className="suggestion-chip">Drug interactions</button>
            <button className="suggestion-chip">Treatment options</button>
            <button className="suggestion-chip">Dosage calculator</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIAssistantTab;
