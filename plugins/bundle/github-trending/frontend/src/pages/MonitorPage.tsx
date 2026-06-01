// 订阅监控 — 顶部订阅列表 + 动态流。

import type * as ReactNS from "react";

const React: typeof ReactNS = window.QwenPaw.host.React;
const { Button, Spin, Empty, Modal, Input, Popconfirm, message } = window.QwenPaw.host.antd;
import { apiDelete, apiGet, apiPost } from "../api";
import { formatNumber, getTimeAgo } from "../utils";

type Sub = {
  id: number;
  target: string;
  enabled: number | boolean;
  last_checked_at?: string | null;
  current_stars?: number | null;
};

type Event = {
  repo_name: string;
  event_type: string;
  title: string;
  body?: string | null;
  stars?: number;
  event_time: string;
};

const EVENT_TAG: Record<string, { icon: string; cls: string }> = {
  release: { icon: "📦", cls: "gh-tag-purple" },
  commit: { icon: "📝", cls: "gh-tag-blue" },
  star_update: { icon: "⭐", cls: "gh-tag-warning" },
  repo_meta_update: { icon: "📌", cls: "" },
  trending_new: { icon: "🔥", cls: "gh-tag-accent" },
  refresh_error: { icon: "⚠️", cls: "gh-tag-warning" },
  collector_error: { icon: "❌", cls: "gh-tag-warning" },
};

export default function MonitorPage() {
  const [subs, setSubs] = React.useState<Sub[]>([]);
  const [events, setEvents] = React.useState<Event[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [modalOpen, setModalOpen] = React.useState(false);
  const [newTarget, setNewTarget] = React.useState("");

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const [s, e] = await Promise.all([
        apiGet("/monitor/subscriptions") as Promise<{ subscriptions?: Sub[] }>,
        apiGet("/monitor/events?limit=50") as Promise<{ events?: Event[] }>,
      ]);
      setSubs(Array.isArray(s?.subscriptions) ? s.subscriptions : []);
      setEvents(Array.isArray(e?.events) ? e.events : []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const add = async () => {
    if (!newTarget.trim()) return;
    try {
      await apiPost(`/monitor/subscriptions?target=${encodeURIComponent(newTarget)}`, {});
      setNewTarget("");
      setModalOpen(false);
      message.success("订阅成功,正在拉取详情...");
      setTimeout(load, 2000);
    } catch (e) {
      message.error("订阅失败");
    }
  };

  const remove = async (id: number) => {
    try {
      await apiDelete(`/monitor/subscriptions/${id}`);
      message.success("已取消");
      load();
    } catch (e) {
      message.error("取消失败");
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <div className="gh-row" style={{ justifyContent: "space-between", marginBottom: 16 }}>
        <h3>📡 我的订阅 ({subs.length})</h3>
        <Button type="primary" onClick={() => setModalOpen(true)}>+ 添加订阅</Button>
      </div>

      {loading ? <Spin /> : subs.length === 0 ? (
        <Empty description="暂无订阅" />
      ) : (
        <table className="gh-table" style={{ marginBottom: 24 }}>
          <thead><tr><th>仓库</th><th>状态</th><th>当前 Stars</th><th>上次检查</th><th style={{ width: 100 }}>操作</th></tr></thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td style={{ fontWeight: 500 }}>{s.target}</td>
                <td>
                  {s.enabled ? <span className="gh-tag gh-tag-accent">监控中</span> : <span className="gh-tag">已暂停</span>}
                </td>
                <td>{s.current_stars != null ? `⭐ ${formatNumber(s.current_stars)}` : "—"}</td>
                <td style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>
                  {s.last_checked_at ? getTimeAgo(s.last_checked_at) : "未拉取"}
                </td>
                <td>
                  <Popconfirm title="确认取消?" onConfirm={() => remove(s.id)}>
                    <Button size="small" danger>删除</Button>
                  </Popconfirm>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3 style={{ marginBottom: 12 }}>📊 监控动态 ({events.length})</h3>
      {events.length === 0 ? (
        <Empty description="暂无动态" />
      ) : (
        <div>
          {events.map((e, i) => {
            const tag = EVENT_TAG[e.event_type] ?? { icon: "📌", cls: "" };
            return (
              <div key={i} className="gh-card" style={{ marginBottom: 8 }}>
                <div className="gh-row" style={{ justifyContent: "space-between" }}>
                  <div className="gh-row">
                    <span style={{ fontWeight: 500 }}>{e.repo_name}</span>
                    <span className={`gh-tag ${tag.cls}`}>{tag.icon} {e.event_type}</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--gh-text-tertiary)" }}>{getTimeAgo(e.event_time)}</span>
                </div>
                <div style={{ marginTop: 6 }}>{e.title}</div>
                {e.body && <div style={{ fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 }}>{e.body}</div>}
              </div>
            );
          })}
        </div>
      )}

      <Modal title="添加订阅" open={modalOpen} onOk={add} onCancel={() => setModalOpen(false)}>
        <Input
          placeholder="owner/repo (例: facebook/react)"
          value={newTarget}
          onChange={(e) => setNewTarget(e.target.value)}
          onPressEnter={add}
        />
      </Modal>
    </div>
  );
}
