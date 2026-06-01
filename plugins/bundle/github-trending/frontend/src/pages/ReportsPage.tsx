// 分析报告 — 表格列表 + 详情 Drawer。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Spin, Empty, Drawer, Button } = window.QwenPaw.host.antd;
import { apiGet } from "../api";

type Report = {
  id: number;
  date: string;
  type: string;
  source: string;
  content?: { overview?: string; highlights?: Array<{ project: string; insight: string }>; trends?: string[]; suggestions?: string[] };
};

export default function ReportsPage() {
  const [reports, setReports] = React.useState<Report[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [selected, setSelected] = React.useState<Report | null>(null);
  const [drawerOpen, setDrawerOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const d = (await apiGet("/reports?limit=50")) as { reports?: Report[] };
      setReports(Array.isArray(d?.reports) ? d.reports : []);
    } catch (e) {
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const open = (r: Report) => {
    setSelected(r);
    setDrawerOpen(true);
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="gh-row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h3>📊 分析报告 ({reports.length})</h3>
        <Button onClick={load}>🔄 刷新</Button>
      </div>
      {loading ? <Spin /> : reports.length === 0 ? (
        <Empty description="暂无报告" />
      ) : (
        <table className="gh-table">
          <thead>
            <tr>
              <th>日期</th>
              <th>类型</th>
              <th>来源</th>
              <th>概览</th>
              <th style={{ width: 80 }}>操作</th>
            </tr>
          </thead>
          <tbody>
            {reports.map((r) => (
              <tr key={r.id}>
                <td>{r.date}</td>
                <td><span className="gh-tag gh-tag-blue">{r.type}</span></td>
                <td>
                  {r.source === "llm" ? (
                    <span className="gh-tag gh-tag-purple">🤖 AI</span>
                  ) : (
                    <span className="gh-tag gh-tag-accent">📝 手动</span>
                  )}
                </td>
                <td style={{ color: "var(--gh-text-secondary)", fontSize: "0.8rem" }}>
                  {r.content?.overview?.slice(0, 80) ?? "—"}
                </td>
                <td>
                  <Button size="small" onClick={() => open(r)}>查看</Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <Drawer title={selected ? `报告 - ${selected.date}` : ""} placement="right" width={560} open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        {selected?.content && (
          <div>
            {selected.content.overview && (
              <>
                <h4>📊 概览</h4>
                <p style={{ color: "var(--gh-text-secondary)" }}>{selected.content.overview}</p>
              </>
            )}
            {selected.content.highlights && selected.content.highlights.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>🔥 亮点项目</h4>
                {selected.content.highlights.map((h, i) => (
                  <div key={i} className="gh-card" style={{ marginBottom: 8 }}>
                    <div style={{ fontWeight: 500 }}>{h.project}</div>
                    <div style={{ fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 }}>{h.insight}</div>
                  </div>
                ))}
              </>
            )}
            {selected.content.trends && selected.content.trends.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>📈 趋势</h4>
                <ul style={{ paddingLeft: 20 }}>
                  {selected.content.trends.map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              </>
            )}
            {selected.content.suggestions && selected.content.suggestions.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>💡 建议</h4>
                <ul style={{ paddingLeft: 20 }}>
                  {selected.content.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                </ul>
              </>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
