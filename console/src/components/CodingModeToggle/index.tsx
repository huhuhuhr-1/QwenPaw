import { useCallback, useState } from "react";
import { Modal } from "antd";
import { Code, FlaskConical, MessageSquare, Bot } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useCodingMode, useProjectDir } from "../../stores/codingModeStore";
import { useAgentStore } from "../../stores/agentStore";
import { useViewModeStore } from "../../stores/viewModeStore";
import { getApiUrl } from "../../api/config";
import { buildAuthHeaders } from "../../api/authHeaders";
import { useNavigate } from "react-router-dom";
import ProjectSelectModal from "../ProjectSelectModal";
import styles from "./index.module.less";

const CONFIRMED_KEY = "qwenpaw-coding-mode-confirmed";

export default function CodingModeToggle() {
  const { t } = useTranslation();
  const { codingMode, initialized, setCodingMode } = useCodingMode();
  const { selectedAgent } = useAgentStore();
  const viewMode = useViewModeStore((s) => s.viewMode);
  const setViewMode = useViewModeStore((s) => s.setViewMode);
  const navigate = useNavigate();
  const { projectDir } = useProjectDir();
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showProjectSelect, setShowProjectSelect] = useState(false);

  const activateCoding = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      await fetch(getApiUrl("/coding-mode"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(),
          "X-Agent-Id": selectedAgent,
        },
        body: JSON.stringify({ enabled: true }),
      });
      setCodingMode(true);
    } catch {
      // Silently ignore
    } finally {
      setLoading(false);
    }
  }, [loading, selectedAgent, setCodingMode]);

  const deactivateCoding = useCallback(async () => {
    if (loading) return;
    setLoading(true);
    try {
      await fetch(getApiUrl("/coding-mode"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...buildAuthHeaders(),
          "X-Agent-Id": selectedAgent,
        },
        body: JSON.stringify({ enabled: false }),
      });
      setCodingMode(false);
    } catch {
      // Silently ignore
    } finally {
      setLoading(false);
    }
  }, [loading, selectedAgent, setCodingMode]);

  const handleCoding = useCallback(async () => {
    // Already in coding mode — toggle off
    if (codingMode) {
      setViewMode("chat");
      await deactivateCoding();
      navigate("/chat");
      return;
    }
    // Enter coding mode — check confirmation + project
    const confirmed = localStorage.getItem(CONFIRMED_KEY);
    if (!confirmed) {
      setShowConfirm(true);
      return;
    }
    if (projectDir === undefined) {
      setShowProjectSelect(true);
      return;
    }
    setViewMode("coding");
    await activateCoding();
    navigate("/coding");
  }, [codingMode, activateCoding, deactivateCoding, projectDir, navigate, setViewMode]);

  const handleChat = useCallback(async () => {
    setViewMode("chat");
    if (codingMode) {
      await deactivateCoding();
    }
    navigate("/chat");
  }, [codingMode, deactivateCoding, navigate, setViewMode]);

  const handleAgent = useCallback(async () => {
    setViewMode("agent");
    if (codingMode) {
      await deactivateCoding();
    }
    navigate("/chat");
  }, [codingMode, deactivateCoding, navigate, setViewMode]);

  const handleConfirm = useCallback(() => {
    localStorage.setItem(CONFIRMED_KEY, "1");
    setShowConfirm(false);
    setShowProjectSelect(true);
  }, []);

  const handleProjectConfirm = useCallback(async () => {
    setShowProjectSelect(false);
    setViewMode("coding");
    await activateCoding();
    navigate("/coding");
  }, [activateCoding, navigate, setViewMode]);

  return (
    <>
      <div className={styles.segmented}>
        <button
          type="button"
          className={`${styles.segment} ${viewMode === "chat" ? styles.segmentActive : ""}`}
          onClick={() => void handleChat()}
          disabled={loading || !initialized}
        >
          <MessageSquare size={14} />
          <span>{t("codingMode.btnChat")}</span>
        </button>
        <button
          type="button"
          className={`${styles.segment} ${viewMode === "coding" ? styles.segmentActive : ""}`}
          onClick={() => void handleCoding()}
          disabled={loading || !initialized}
        >
          <Code size={14} />
          <span>{t("codingMode.btnCode")}</span>
        </button>
        <button
          type="button"
          className={`${styles.segment} ${viewMode === "agent" ? styles.segmentActive : ""}`}
          onClick={() => void handleAgent()}
        >
          <Bot size={14} />
          <span>{t("codingMode.btnAgent", "智能体")}</span>
        </button>
      </div>

      {/* Step 1: Experimental warning */}
      <Modal
        open={showConfirm}
        title={
          <span className={styles.modalTitle}>
            <FlaskConical size={16} className={styles.flaskIcon} />
            {t("codingMode.experimental")}
          </span>
        }
        okText={t("codingMode.confirmBtn")}
        cancelText={t("common.cancel")}
        onOk={handleConfirm}
        onCancel={() => setShowConfirm(false)}
        confirmLoading={loading}
        width={440}
      >
        <div className={styles.modalBody}>
          <p className={styles.modalDesc}>
            {t("codingMode.experimentalDesc")}
          </p>
          <p className={styles.modalNote}>
            {t("codingMode.experimentalNote")}
          </p>
        </div>
      </Modal>

      {/* Step 2: Project selection */}
      <ProjectSelectModal
        open={showProjectSelect}
        onClose={() => {
          setShowProjectSelect(false);
          void handleProjectConfirm();
        }}
        onConfirm={() => void handleProjectConfirm()}
      />
    </>
  );
}