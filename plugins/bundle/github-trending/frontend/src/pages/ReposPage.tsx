// 仓库搜索 — 顶部搜索 + 表格 + 详情 Drawer。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Input, Spin, Empty, Drawer, Button, message } = window.QwenPaw.host.antd;
import { apiGet, apiPost } from "../api";
import { formatNumber } from "../utils";

type Repo = {
  full_name: string;
  description?: string | null;
  language?: string | null;
  stars: number;
  forks: number;
  appearances?: number;
  url?: string;
  first_seen?: string | null;
  last_seen?: string | null;
};

type Trend = { date: string; rank: number; stars: number; stars_delta?: number };

export default function ReposPage() {
  const [keyword, setKeyword] = React.useState("");
  const [results, setResults] = React.useState<Repo[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selected, setSelected] = React.useState<Repo | null>(null);
  const [trend, setTrend] = React.useState<Trend[]>([]);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const search = async (k: string) => {
    if (!k.trim()) return;
    setLoading(true);
    try {
      const d = (await apiGet(`/repos/search?keyword=${encodeURIComponent(k)}`)) as { repos?: Repo[] };
      setResults(Array.isArray(d?.repos) ? d.repos : []);
    } catch (e) {
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const open = async (r: Repo) => {
    setSelected(r);
    setDrawerOpen(true);
    try {
      const d = (await apiGet(`/repos/${encodeURIComponent(r.full_name)}/trend`)) as { trend?: Trend[] };
      setTrend(Array.isArray(d?.trend) ? d.trend : []);
    } catch (e) {
      setTrend([]);
    }
  };

  const subscribe = async () => {
    if (!selected) return;
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(selected.full_name)}`, {});
      message.success("已订阅");
    } catch (e) {
      message.error("订阅失败");
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <Input.Search
        placeholder="搜索项目名 / 描述..."
        enterButton="搜索"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        onSearch={search}
        style={{ maxWidth: 480, marginBottom: 16 }}
      />
      {loading ? (
        <div style={{ padding: 32, textAlign: "center" }}><Spin /></div>
      ) : results.length === 0 ? (
        <Empty description="输入关键词搜索" />
      ) : (
        <table className="gh-table">
          <thead>
            <tr>
              <th>仓库</th>
              <th>语言</th>
              <th style={{ textAlign: "right" }}>Stars</th>
              <th style={{ textAlign: "right" }}>Forks</th>
              <th style={{ textAlign: "right" }}>上榜次数</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r) => (
              <tr key={r.full_name} onClick={() => open(r)}>
                <td>
                  <div style={{ fontWeight: 500 }}>{r.full_name}</div>
                  {r.description && (
                    <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>{r.description.slice(0, 80)}</div>
                  )}
                </td>
                <td>{r.language ? <span className="gh-tag gh-tag-blue">{r.language}</span> : "—"}</td>
                <td style={{ textAlign: "right" }}>⭐ {formatNumber(r.stars)}</td>
                <td style={{ textAlign: "right" }}>🍴 {formatNumber(r.forks)}</td>
                <td style={{ textAlign: "right" }}>{r.appearances ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Drawer
        title={selected?.full_name}
        placement="right"
        width={480}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {selected && (
          <div>
            <Button type="primary" onClick={subscribe} style={{ marginBottom: 16 }}>+ 订阅</Button>
            <p style={{ color: "var(--gh-text-secondary)" }}>{selected.description ?? "—"}</p>
            <div className="gh-card" style={{ marginBottom: 16 }}>
              <div>⭐ {formatNumber(selected.stars)} stars · 🍴 {formatNumber(selected.forks)} forks</div>
              <div style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 8 }}>
                首次上榜: {selected.first_seen ?? "—"} · 最近上榜: {selected.last_seen ?? "—"}
              </div>
            </div>
            <h4 style={{ marginBottom: 8 }}>趋势 (近 10 天)</h4>
            {trend.length === 0 ? <div style={{ color: "var(--gh-text-tertiary)" }}>暂无趋势</div> : (
              <ul style={{ listStyle: "none", padding: 0 }}>
                {trend.slice(0, 10).map((t) => (
                  <li key={t.date} style={{ padding: "6px 0", borderBottom: "1px solid var(--gh-border)" }}>
                    <span className="gh-tag">{t.date}</span>
                    <span style={{ marginLeft: 12 }}>排名 #{t.rank} · ⭐ {formatNumber(t.stars)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
