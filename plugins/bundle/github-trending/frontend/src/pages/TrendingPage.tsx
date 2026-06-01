// 热榜 — 左侧 180px 日期侧栏 + 右侧仓库表格。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Spin, Empty, Button, message } = window.QwenPaw.host.antd;
import { apiGet, apiPost } from "../api";
import { formatNumber, LANGUAGES, localDateString } from "../utils";

type TrendingItem = {
  rank: number;
  full_name: string;
  description?: string | null;
  language?: string | null;
  stars: number;
  stars_delta: number;
  forks: number;
  url: string;
};

type TrendingData = {
  date: string;
  language: string;
  total_count: number;
  items: TrendingItem[];
};

function formatDate(d: string): string {
  // 用本地日期比较(避免 UTC 偏移 bug:UTC+8 早上 0-8 点时 toISOString 还在昨天)
  const today = localDateString();
  const yest = localDateString(new Date(Date.now() - 86400000));
  if (d === today) return `${d} 今天`;
  if (d === yest) return `${d} 昨天`;
  return d;
}

export default function TrendingPage() {
  const [dates, setDates] = React.useState<string[]>([]);
  const [selectedDate, setSelectedDate] = React.useState<string>("");
  const [language, setLanguage] = React.useState<string>("");
  const [data, setData] = React.useState<TrendingData | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [subscribing, setSubscribing] = React.useState<string | null>(null);

  React.useEffect(() => {
    apiGet(`/trending/dates?language=${encodeURIComponent(language || "all")}`)
      .then((d: unknown) => {
        const list = Array.isArray(d) ? (d as string[]) : [];
        setDates(list);
        if (list.length > 0 && !selectedDate) setSelectedDate(list[0]);
      })
      .catch(console.error);
  }, [language]);

  React.useEffect(() => {
    if (!selectedDate) return;
    setLoading(true);
    apiGet(
      `/trending/daily?date=${encodeURIComponent(selectedDate)}&language=${encodeURIComponent(language || "all")}`,
    )
      .then((d: unknown) => setData((d as TrendingData) ?? null))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [selectedDate, language]);

  const subscribe = async (fullName: string) => {
    setSubscribing(fullName);
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(fullName)}`, {});
      message.success(`已订阅 ${fullName}`);
    } catch (e) {
      message.error("订阅失败");
    } finally {
      setSubscribing(null);
    }
  };

  return (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "180px 1fr", gap: 16, minHeight: 500 }}>
      <div className="gh-card" style={{ padding: 0, overflow: "hidden", maxHeight: 600, overflowY: "auto" }}>
        <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--gh-border)", fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>
          📅 日期({dates.length})
        </div>
        {dates.length === 0 ? (
          <div style={{ padding: 16, color: "var(--gh-text-tertiary)", fontSize: "0.8rem", textAlign: "center" }}>暂无数据</div>
        ) : (
          dates.map((d) => (
            <button
              key={d}
              onClick={() => setSelectedDate(d)}
              style={{
                width: "100%", padding: "8px 14px", background: selectedDate === d ? "var(--gh-elevated)" : "transparent",
                border: "none", borderLeft: selectedDate === d ? "2px solid var(--gh-accent)" : "2px solid transparent",
                color: selectedDate === d ? "var(--gh-text)" : "var(--gh-text-secondary)",
                fontSize: "0.85rem", textAlign: "left", cursor: "pointer",
              }}
            >
              {formatDate(d)}
            </button>
          ))
        )}
      </div>

      <div className="gh-card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--gh-border)", display: "flex", alignItems: "center", gap: 12 }}>
          <h4 style={{ margin: 0 }}>{selectedDate ? formatDate(selectedDate) : "选择日期"}</h4>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            style={{ background: "var(--gh-elevated)", color: "var(--gh-text)", border: "1px solid var(--gh-border)", borderRadius: 6, padding: "4px 8px", fontSize: "0.8rem" }}
          >
            {LANGUAGES.map((l) => (
              <option key={l.value} value={l.value}>{l.label}</option>
            ))}
          </select>
          <span style={{ marginLeft: "auto", color: "var(--gh-text-tertiary)", fontSize: "0.75rem" }}>
            {data?.items.length ?? 0} 个仓库
          </span>
        </div>

        {loading ? (
          <div style={{ padding: 32, textAlign: "center" }}><Spin /></div>
        ) : !data || data.items.length === 0 ? (
          <Empty description="暂无数据" style={{ padding: 32 }} />
        ) : (
          <table className="gh-table">
            <thead>
              <tr>
                <th style={{ width: 40 }}>#</th>
                <th>仓库</th>
                <th>语言</th>
                <th style={{ textAlign: "right" }}>Stars</th>
                <th style={{ textAlign: "right" }}>今日涨</th>
                <th style={{ textAlign: "center", width: 100 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.full_name}>
                  <td style={{ color: "var(--gh-text-tertiary)" }}>{item.rank}</td>
                  <td>
                    <a href={item.url} target="_blank" rel="noreferrer" style={{ fontWeight: 500 }}>
                      {item.full_name}
                    </a>
                    {item.description && (
                      <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 2 }}>
                        {item.description.slice(0, 80)}
                      </div>
                    )}
                  </td>
                  <td>
                    {item.language ? (
                      <span className="gh-tag gh-tag-blue">{item.language}</span>
                    ) : (
                      <span className="gh-text-tertiary">—</span>
                    )}
                  </td>
                  <td style={{ textAlign: "right" }}>⭐ {formatNumber(item.stars)}</td>
                  <td style={{ textAlign: "right" }}>
                    {item.stars_delta > 0 ? (
                      <span className="gh-tag gh-tag-accent">+{formatNumber(item.stars_delta)}</span>
                    ) : (
                      <span className="gh-text-tertiary">—</span>
                    )}
                  </td>
                  <td style={{ textAlign: "center" }}>
                    <Button
                      size="small"
                      loading={subscribing === item.full_name}
                      onClick={() => subscribe(item.full_name)}
                    >
                      订阅
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
