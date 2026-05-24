import { useState, useEffect, useMemo } from "react";
import { Input } from "antd";
import { SparkSearchLine } from "@agentscope-ai/icons";
import { useAgentStore } from "../stores/agentStore";
import { agentsApi } from "../api/modules/agents";
import { consoleApi } from "../api/modules/console";
import type { AgentSummary } from "../api/types/agents";
import styles from "./AgentSidebar.module.less";

interface Props {
  onAgentChange?: (agentId: string) => void;
}

const AVATAR_COLORS = [
  "linear-gradient(135deg, #ff7f16, #ffb366)",
  "linear-gradient(135deg, #3b82f6, #60a5fa)",
  "linear-gradient(135deg, #22c55e, #4ade80)",
  "linear-gradient(135deg, #a855f7, #c084fc)",
  "linear-gradient(135deg, #ef4444, #f87171)",
  "linear-gradient(135deg, #f59e0b, #fbbf24)",
  "linear-gradient(135deg, #06b6d4, #22d3ee)",
];

function getAvatarStyle(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function getInitials(name: string): string {
  return name.slice(0, 2);
}

export default function AgentSidebar({ onAgentChange }: Props) {
  const [search, setSearch] = useState("");
  const { agents, selectedAgent, unreadCountByAgent, setSelectedAgent, setAgents, clearUnread } = useAgentStore();

  useEffect(() => {
    agentsApi.listAgents()
      .then((res) => setAgents(res.agents))
      .catch(() => {});
  }, []);

  const filteredAgents = useMemo(() => {
    if (!search.trim()) return agents;
    const q = search.toLowerCase();
    return agents.filter(
      (a) =>
        a.name.toLowerCase().includes(q) ||
        (a.description || "").toLowerCase().includes(q),
    );
  }, [agents, search]);

  const handleSelect = (agent: AgentSummary) => {
    setSelectedAgent(agent.id);
    clearUnread(agent.id);
    consoleApi.clearUnread(agent.id).catch(() => {});
    onAgentChange?.(agent.id);
  };

  return (
    <div className={styles.sidebar}>
      <div className={styles.header}>
        <span className={styles.headerTitle}>智能体</span>
      </div>

      <div className={styles.searchWrap}>
        <Input
          prefix={<SparkSearchLine size={14} style={{ color: "rgba(255,255,255,0.35)" }} />}
          placeholder="搜索智能体..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={styles.searchInput}
          allowClear
        />
      </div>

      <div className={styles.list}>
        {filteredAgents.length === 0 && (
          <div className={styles.empty}>暂无智能体</div>
        )}
        {filteredAgents.map((agent) => (
          <div
            key={agent.id}
            className={`${styles.card} ${selectedAgent === agent.id ? styles.cardSelected : ""}`}
            onClick={() => handleSelect(agent)}
          >
            <div className={styles.avatarWrap}>
              <div
                className={styles.avatar}
                style={{ background: getAvatarStyle(agent.name) }}
              >
                {getInitials(agent.name)}
              </div>
              {unreadCountByAgent[agent.id] ? (
                <span className={styles.badge}>
                  {unreadCountByAgent[agent.id] > 99
                    ? "99+"
                    : unreadCountByAgent[agent.id]}
                </span>
              ) : null}
            </div>
            <div className={styles.info}>
              <div className={styles.name}>{agent.name}</div>
              <div className={styles.desc}>
                {agent.description || "暂无描述"}
              </div>
            </div>
            <div className={`${styles.status} ${agent.enabled ? styles.statusOnline : styles.statusOffline}`} />
          </div>
        ))}
      </div>
    </div>
  );
}
