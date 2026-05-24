import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAgentStore } from "../stores/agentStore";
import ChatPage from "../pages/Chat";
import { useLocation } from "react-router-dom";
import styles from "./AgentChatView.module.less";

export default function AgentChatView() {
  const { agents, selectedAgent, setLastChatId, getLastChatId } =
    useAgentStore();
  const location = useLocation();
  const navigate = useNavigate();

  const currentAgent = agents.find((a) => a.id === selectedAgent) ?? null;

  // Track previous agent to save per-agent session
  const prevAgentRef = useRef(selectedAgent);

  useEffect(() => {
    const prevAgent = prevAgentRef.current;
    if (prevAgent === selectedAgent) return;
    prevAgentRef.current = selectedAgent;

    // Extract current chat id from URL (e.g. /chat/<id>)
    const match = location.pathname.match(/^\/chat(?:\/(.+))?$/);
    const currentChatId = match?.[1] || null;

    // Save current chat for the agent we're leaving
    if (currentChatId && prevAgent) {
      setLastChatId(prevAgent, currentChatId);
    }

    // Navigate to the new agent's last chat (or /chat for new session)
    const lastChatId = getLastChatId(selectedAgent);
    navigate(lastChatId ? `/chat/${lastChatId}` : "/chat", { replace: true });
  }, [selectedAgent, setLastChatId, getLastChatId, navigate, location.pathname]);

  return (
    <div className={styles.wrap}>
      <div className={styles.header}>
        <div className={styles.headerInfo}>
          <div className={styles.agentName}>
            {currentAgent?.name ?? "智能体"}
          </div>
          <div className={styles.agentStatus}>
            <span
              className={`${styles.statusDot} ${
                currentAgent?.enabled
                  ? styles.statusOnline
                  : styles.statusOffline
              }`}
            />
            {currentAgent?.enabled ? "在线" : "离线"}
          </div>
        </div>
      </div>

      <div className={styles.chatContent}>
        <ChatPage />
      </div>
    </div>
  );
}
