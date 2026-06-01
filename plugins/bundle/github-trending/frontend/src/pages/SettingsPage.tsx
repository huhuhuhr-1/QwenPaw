// 设置页 — 采集频率、周期、语言、立即触发。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Switch, InputNumber, Radio, Select, Button, message, Spin } =
  window.QwenPaw.host.antd;
import { apiGet, apiPost, apiPut } from "../api";

const PRESET_MINUTES = [30, 60, 180, 360, 720, 1440];

const PRESET_LANGS = [
  { value: "", label: "全部" },
  { value: "python", label: "Python" },
  { value: "go", label: "Go" },
  { value: "rust", label: "Rust" },
  { value: "typescript", label: "TypeScript" },
  { value: "javascript", label: "JavaScript" },
  { value: "java", label: "Java" },
  { value: "html", label: "HTML" },
];

type RuntimeSettings = {
  collect_enabled: boolean;
  collect_interval_min: number;
  collect_period: string;
  collect_languages: string[];
};

type TriggerStatus = {
  task_id: string;
  status: "running" | "done" | "timeout" | "error";
  result?: {
    ok: string[];
    errors: Array<{ lang: string; error: string }>;
    date: string;
  };
  error?: string;
};

export default function SettingsPage() {
  const [loading, setLoading] = React.useState(true);
  const [settings, setSettings] = React.useState<RuntimeSettings | null>(null);
  const [interval, setInterval] = React.useState<number>(60);
  const [enabled, setEnabled] = React.useState<boolean>(true);
  const [period, setPeriod] = React.useState<string>("daily");
  const [languages, setLanguages] = React.useState<string[]>([""]);
  const [triggering, setTriggering] = React.useState(false);
  const [taskId, setTaskId] = React.useState<string | null>(null);
  const [lastRun, setLastRun] = React.useState<TriggerStatus["result"] | null>(
    null
  );

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const d = (await apiGet("/settings")) as RuntimeSettings;
      setSettings(d);
      setEnabled(d.collect_enabled);
      setInterval(d.collect_interval_min);
      setPeriod(d.collect_period);
      setLanguages(d.collect_languages);
    } catch (e) {
      message.error("加载设置失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const save = async (overrides: Partial<RuntimeSettings> = {}) => {
    const payload = {
      collect_enabled: overrides.collect_enabled ?? enabled,
      collect_interval_min: overrides.collect_interval_min ?? interval,
      collect_period: overrides.collect_period ?? period,
      collect_languages: overrides.collect_languages ?? languages,
    };
    try {
      await apiPut("/settings", payload);
      message.success("已保存");
      await load();
    } catch (e) {
      message.error("保存失败");
    }
  };

  const onEnableChange = async (v: boolean) => {
    setEnabled(v);
    await save({ collect_enabled: v });
  };

  const onIntervalChange = async (v: number | null) => {
    if (v == null) return;
    setInterval(v);
    await save({ collect_interval_min: v });
  };

  const onPeriodChange = async (e: ReactNS.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setPeriod(v);
    await save({ collect_period: v });
  };

  const onLanguagesChange = async (v: string[]) => {
    setLanguages(v);
    await save({ collect_languages: v });
  };

  const triggerCollect = async () => {
    setTriggering(true);
    setTaskId(null);
    try {
      const r = (await apiPost("/settings/trigger-collect", {})) as {
        task_id: string;
      };
      setTaskId(r.task_id);
      pollStatus(r.task_id);
    } catch (e) {
      message.error("触发失败");
      setTriggering(false);
    }
  };

  const pollStatus = async (tid: string) => {
    const start = Date.now();
    const tick = async (): Promise<void> => {
      try {
        const s = (await apiGet(
          `/settings/trigger-collect/${tid}`
        )) as TriggerStatus;
        if (s.status === "done") {
          setLastRun(s.result ?? null);
          setTriggering(false);
          message.success(
            `采集完成: ${s.result?.ok.length ?? 0} 个语言成功`
          );
        } else if (s.status === "error" || s.status === "timeout") {
          setTriggering(false);
          message.error(`采集${s.status === "timeout" ? "超时" : "失败"}`);
        } else if (Date.now() - start > 6 * 60 * 1000) {
          setTriggering(false);
          message.error("轮询超时");
        } else {
          setTimeout(tick, 3000);
        }
      } catch (e) {
        setTriggering(false);
        message.error("查状态失败");
      }
    };
    tick();
  };

  if (loading || !settings) {
    return (
      <div style={{ padding: 32, textAlign: "center" }}>
        <Spin />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <h2 style={{ marginBottom: 24 }}>⚙️ 采集设置</h2>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>启用采集</h4>
        <Switch checked={enabled} onChange={onEnableChange} />
        <span className="gh-text-secondary" style={{ marginLeft: 12 }}>
          {enabled ? "✅ 运行中" : "⏸ 已暂停"}
        </span>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>采集频率</h4>
        <InputNumber
          value={interval}
          onChange={onIntervalChange}
          min={5}
          max={10080}
          addonAfter="分钟"
        />
        <div
          style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}
        >
          {PRESET_MINUTES.map((m) => (
            <button
              key={m}
              className={`gh-button ${
                interval === m ? "gh-button-primary" : ""
              }`}
              onClick={() => onIntervalChange(m)}
            >
              {m < 60
                ? `${m}分`
                : m < 1440
                ? `${m / 60}时`
                : `${m / 1440}天`}
            </button>
          ))}
        </div>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>周期</h4>
        <Radio.Group
          value={period}
          onChange={onPeriodChange}
          style={{ display: "flex", gap: 8 }}
        >
          <Radio value="daily">Daily</Radio>
          <Radio value="weekly">Weekly</Radio>
          <Radio value="monthly">Monthly</Radio>
        </Radio.Group>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>抓取语言</h4>
        <Select
          mode="multiple"
          value={languages}
          onChange={onLanguagesChange}
          style={{ width: "100%" }}
          options={PRESET_LANGS}
        />
        <p
          className="gh-text-tertiary"
          style={{ fontSize: "0.75rem", marginTop: 8 }}
        >
          留「全部」代表 github.com/trending 主页(不限定语言)
        </p>
      </section>

      <section className="gh-card" style={{ marginBottom: 16 }}>
        <h4 style={{ marginBottom: 12 }}>状态</h4>
        {lastRun ? (
          <div
            className="gh-text-secondary"
            style={{ fontSize: "0.85rem" }}
          >
            上次运行: {lastRun.date} · ✅ {lastRun.ok.length} 成功
            {lastRun.errors.length > 0 && (
              <span
                className="gh-tag gh-tag-warning"
                style={{ marginLeft: 8 }}
              >
                ❌ {lastRun.errors.length} 失败
              </span>
            )}
          </div>
        ) : (
          <div
            className="gh-text-tertiary"
            style={{ fontSize: "0.85rem" }}
          >
            还没手动触发过采集
          </div>
        )}
      </section>

      <div style={{ display: "flex", gap: 12 }}>
        <Button
          type="primary"
          loading={triggering}
          onClick={triggerCollect}
          disabled={!enabled}
        >
          🚀 立即采集一次
        </Button>
        <Button onClick={load}>🔄 刷新状态</Button>
      </div>
    </div>
  );
}
