const X = window.QwenPaw.host, se = X.getApiUrl, F = X.getApiToken;
function ce() {
  var g;
  const a = {}, d = F == null ? void 0 : F();
  d && (a.Authorization = `Bearer ${d}`);
  try {
    const p = sessionStorage.getItem("qwenpaw-agent-storage") || localStorage.getItem("qwenpaw-agent-storage");
    if (p) {
      const c = JSON.parse(p), v = (g = c == null ? void 0 : c.state) == null ? void 0 : g.selectedAgent;
      v && (a["X-Agent-Id"] = v);
    }
  } catch (p) {
    console.warn("Failed to read selected agent from storage:", p);
  }
  return a;
}
async function z(a, d = {}) {
  const g = await fetch(se(a), {
    ...d,
    headers: { ...ce(), ...d.headers ?? {} }
  });
  if (!g.ok)
    throw new Error(`${g.status} ${await g.text()}`);
  return g.json();
}
async function k(a) {
  return z(a);
}
async function I(a, d) {
  return z(a, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(d)
  });
}
async function ie(a) {
  return z(a, { method: "DELETE" });
}
async function ge(a, d) {
  return z(a, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(d)
  });
}
function Q(a = /* @__PURE__ */ new Date()) {
  return a.getFullYear() + "-" + String(a.getMonth() + 1).padStart(2, "0") + "-" + String(a.getDate()).padStart(2, "0");
}
function A(a) {
  return a >= 1e3 ? (a / 1e3).toFixed(1) + "k" : a.toString();
}
function U(a) {
  const d = /* @__PURE__ */ new Date(), g = new Date(a), p = Math.floor((d.getTime() - g.getTime()) / 1e3);
  return p < 60 ? "刚刚" : p < 3600 ? Math.floor(p / 60) + "分钟前" : p < 86400 ? Math.floor(p / 3600) + "小时前" : Math.floor(p / 86400) + "天前";
}
const me = [
  { value: "all", label: "全部语言" },
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "rust", label: "Rust" },
  { value: "go", label: "Go" },
  { value: "java", label: "Java" },
  { value: "html", label: "HTML" }
], n = window.QwenPaw.host.React, { Spin: de, Empty: he, Button: ue, message: j } = window.QwenPaw.host.antd;
function W(a) {
  const d = Q(), g = Q(new Date(Date.now() - 864e5));
  return a === d ? `${a} 今天` : a === g ? `${a} 昨天` : a;
}
function pe() {
  const [a, d] = n.useState([]), [g, p] = n.useState(""), [c, v] = n.useState(""), [h, w] = n.useState(null), [f, S] = n.useState(!1), [i, y] = n.useState(null);
  n.useEffect(() => {
    k(`/trending/dates?language=${encodeURIComponent(c || "all")}`).then((e) => {
      const b = Array.isArray(e) ? e : [];
      d(b), b.length > 0 && !g && p(b[0]);
    }).catch(console.error);
  }, [c]), n.useEffect(() => {
    g && (S(!0), k(
      `/trending/daily?date=${encodeURIComponent(g)}&language=${encodeURIComponent(c || "all")}`
    ).then((e) => w(e ?? null)).catch(() => w(null)).finally(() => S(!1)));
  }, [g, c]);
  const $ = async (e) => {
    y(e);
    try {
      await I(`/monitor/subscriptions?target=${encodeURIComponent(e)}`, {}), j.success(`已订阅 ${e}`);
    } catch {
      j.error("订阅失败");
    } finally {
      y(null);
    }
  };
  return /* @__PURE__ */ n.createElement("div", { style: { padding: 16, display: "grid", gridTemplateColumns: "180px 1fr", gap: 16, minHeight: 500 } }, /* @__PURE__ */ n.createElement("div", { className: "gh-card", style: { padding: 0, overflow: "hidden", maxHeight: 600, overflowY: "auto" } }, /* @__PURE__ */ n.createElement("div", { style: { padding: "10px 12px", borderBottom: "1px solid var(--gh-border)", fontSize: "0.75rem", color: "var(--gh-text-tertiary)" } }, "📅 日期(", a.length, ")"), a.length === 0 ? /* @__PURE__ */ n.createElement("div", { style: { padding: 16, color: "var(--gh-text-tertiary)", fontSize: "0.8rem", textAlign: "center" } }, "暂无数据") : a.map((e) => /* @__PURE__ */ n.createElement(
    "button",
    {
      key: e,
      onClick: () => p(e),
      style: {
        width: "100%",
        padding: "8px 14px",
        background: g === e ? "var(--gh-elevated)" : "transparent",
        border: "none",
        borderLeft: g === e ? "2px solid var(--gh-accent)" : "2px solid transparent",
        color: g === e ? "var(--gh-text)" : "var(--gh-text-secondary)",
        fontSize: "0.85rem",
        textAlign: "left",
        cursor: "pointer"
      }
    },
    W(e)
  ))), /* @__PURE__ */ n.createElement("div", { className: "gh-card", style: { padding: 0, overflow: "hidden" } }, /* @__PURE__ */ n.createElement("div", { style: { padding: "12px 16px", borderBottom: "1px solid var(--gh-border)", display: "flex", alignItems: "center", gap: 12 } }, /* @__PURE__ */ n.createElement("h4", { style: { margin: 0 } }, g ? W(g) : "选择日期"), /* @__PURE__ */ n.createElement(
    "select",
    {
      value: c,
      onChange: (e) => v(e.target.value),
      style: { background: "var(--gh-elevated)", color: "var(--gh-text)", border: "1px solid var(--gh-border)", borderRadius: 6, padding: "4px 8px", fontSize: "0.8rem" }
    },
    me.map((e) => /* @__PURE__ */ n.createElement("option", { key: e.value, value: e.value }, e.label))
  ), /* @__PURE__ */ n.createElement("span", { style: { marginLeft: "auto", color: "var(--gh-text-tertiary)", fontSize: "0.75rem" } }, (h == null ? void 0 : h.items.length) ?? 0, " 个仓库")), f ? /* @__PURE__ */ n.createElement("div", { style: { padding: 32, textAlign: "center" } }, /* @__PURE__ */ n.createElement(de, null)) : !h || h.items.length === 0 ? /* @__PURE__ */ n.createElement(he, { description: "暂无数据", style: { padding: 32 } }) : /* @__PURE__ */ n.createElement("table", { className: "gh-table" }, /* @__PURE__ */ n.createElement("thead", null, /* @__PURE__ */ n.createElement("tr", null, /* @__PURE__ */ n.createElement("th", { style: { width: 40 } }, "#"), /* @__PURE__ */ n.createElement("th", null, "仓库"), /* @__PURE__ */ n.createElement("th", null, "语言"), /* @__PURE__ */ n.createElement("th", { style: { textAlign: "right" } }, "Stars"), /* @__PURE__ */ n.createElement("th", { style: { textAlign: "right" } }, "今日涨"), /* @__PURE__ */ n.createElement("th", { style: { textAlign: "center", width: 100 } }, "操作"))), /* @__PURE__ */ n.createElement("tbody", null, h.items.map((e) => /* @__PURE__ */ n.createElement("tr", { key: e.full_name }, /* @__PURE__ */ n.createElement("td", { style: { color: "var(--gh-text-tertiary)" } }, e.rank), /* @__PURE__ */ n.createElement("td", null, /* @__PURE__ */ n.createElement("a", { href: e.url, target: "_blank", rel: "noreferrer", style: { fontWeight: 500 } }, e.full_name), e.description && /* @__PURE__ */ n.createElement("div", { style: { fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 2 } }, e.description.slice(0, 80))), /* @__PURE__ */ n.createElement("td", null, e.language ? /* @__PURE__ */ n.createElement("span", { className: "gh-tag gh-tag-blue" }, e.language) : /* @__PURE__ */ n.createElement("span", { className: "gh-text-tertiary" }, "—")), /* @__PURE__ */ n.createElement("td", { style: { textAlign: "right" } }, "⭐ ", A(e.stars)), /* @__PURE__ */ n.createElement("td", { style: { textAlign: "right" } }, e.stars_delta > 0 ? /* @__PURE__ */ n.createElement("span", { className: "gh-tag gh-tag-accent" }, "+", A(e.stars_delta)) : /* @__PURE__ */ n.createElement("span", { className: "gh-text-tertiary" }, "—")), /* @__PURE__ */ n.createElement("td", { style: { textAlign: "center" } }, /* @__PURE__ */ n.createElement(
    ue,
    {
      size: "small",
      loading: i === e.full_name,
      onClick: () => $(e.full_name)
    },
    "订阅"
  ))))))));
}
const l = window.QwenPaw.host.React, { Input: ye, Spin: Ee, Empty: ve, Drawer: fe, Button: be, message: G } = window.QwenPaw.host.antd;
function we() {
  const [a, d] = l.useState(""), [g, p] = l.useState([]), [c, v] = l.useState(!1), [h, w] = l.useState(null), [f, S] = l.useState([]), [i, y] = l.useState(!1), $ = async (m) => {
    if (m.trim()) {
      v(!0);
      try {
        const E = await k(`/repos/search?keyword=${encodeURIComponent(m)}`);
        p(Array.isArray(E == null ? void 0 : E.repos) ? E.repos : []);
      } catch {
        p([]);
      } finally {
        v(!1);
      }
    }
  }, e = async (m) => {
    w(m), y(!0);
    try {
      const E = await k(`/repos/${encodeURIComponent(m.full_name)}/trend`);
      S(Array.isArray(E == null ? void 0 : E.trend) ? E.trend : []);
    } catch {
      S([]);
    }
  }, b = async () => {
    if (h)
      try {
        await I(`/monitor/subscriptions?target=${encodeURIComponent(h.full_name)}`, {}), G.success("已订阅");
      } catch {
        G.error("订阅失败");
      }
  };
  return /* @__PURE__ */ l.createElement("div", { style: { padding: 16 } }, /* @__PURE__ */ l.createElement(
    ye.Search,
    {
      placeholder: "搜索项目名 / 描述...",
      enterButton: "搜索",
      value: a,
      onChange: (m) => d(m.target.value),
      onSearch: $,
      style: { maxWidth: 480, marginBottom: 16 }
    }
  ), c ? /* @__PURE__ */ l.createElement("div", { style: { padding: 32, textAlign: "center" } }, /* @__PURE__ */ l.createElement(Ee, null)) : g.length === 0 ? /* @__PURE__ */ l.createElement(ve, { description: "输入关键词搜索" }) : /* @__PURE__ */ l.createElement("table", { className: "gh-table" }, /* @__PURE__ */ l.createElement("thead", null, /* @__PURE__ */ l.createElement("tr", null, /* @__PURE__ */ l.createElement("th", null, "仓库"), /* @__PURE__ */ l.createElement("th", null, "语言"), /* @__PURE__ */ l.createElement("th", { style: { textAlign: "right" } }, "Stars"), /* @__PURE__ */ l.createElement("th", { style: { textAlign: "right" } }, "Forks"), /* @__PURE__ */ l.createElement("th", { style: { textAlign: "right" } }, "上榜次数"))), /* @__PURE__ */ l.createElement("tbody", null, g.map((m) => /* @__PURE__ */ l.createElement("tr", { key: m.full_name, onClick: () => e(m) }, /* @__PURE__ */ l.createElement("td", null, /* @__PURE__ */ l.createElement("div", { style: { fontWeight: 500 } }, m.full_name), m.description && /* @__PURE__ */ l.createElement("div", { style: { fontSize: "0.75rem", color: "var(--gh-text-tertiary)" } }, m.description.slice(0, 80))), /* @__PURE__ */ l.createElement("td", null, m.language ? /* @__PURE__ */ l.createElement("span", { className: "gh-tag gh-tag-blue" }, m.language) : "—"), /* @__PURE__ */ l.createElement("td", { style: { textAlign: "right" } }, "⭐ ", A(m.stars)), /* @__PURE__ */ l.createElement("td", { style: { textAlign: "right" } }, "🍴 ", A(m.forks)), /* @__PURE__ */ l.createElement("td", { style: { textAlign: "right" } }, m.appearances ?? 0))))), /* @__PURE__ */ l.createElement(
    fe,
    {
      title: h == null ? void 0 : h.full_name,
      placement: "right",
      width: 480,
      open: i,
      onClose: () => y(!1)
    },
    h && /* @__PURE__ */ l.createElement("div", null, /* @__PURE__ */ l.createElement(be, { type: "primary", onClick: b, style: { marginBottom: 16 } }, "+ 订阅"), /* @__PURE__ */ l.createElement("p", { style: { color: "var(--gh-text-secondary)" } }, h.description ?? "—"), /* @__PURE__ */ l.createElement("div", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ l.createElement("div", null, "⭐ ", A(h.stars), " stars · 🍴 ", A(h.forks), " forks"), /* @__PURE__ */ l.createElement("div", { style: { fontSize: "0.75rem", color: "var(--gh-text-tertiary)", marginTop: 8 } }, "首次上榜: ", h.first_seen ?? "—", " · 最近上榜: ", h.last_seen ?? "—")), /* @__PURE__ */ l.createElement("h4", { style: { marginBottom: 8 } }, "趋势 (近 10 天)"), f.length === 0 ? /* @__PURE__ */ l.createElement("div", { style: { color: "var(--gh-text-tertiary)" } }, "暂无趋势") : /* @__PURE__ */ l.createElement("ul", { style: { listStyle: "none", padding: 0 } }, f.slice(0, 10).map((m) => /* @__PURE__ */ l.createElement("li", { key: m.date, style: { padding: "6px 0", borderBottom: "1px solid var(--gh-border)" } }, /* @__PURE__ */ l.createElement("span", { className: "gh-tag" }, m.date), /* @__PURE__ */ l.createElement("span", { style: { marginLeft: 12 } }, "排名 #", m.rank, " · ⭐ ", A(m.stars))))))
  ));
}
const r = window.QwenPaw.host.React, { Button: J, Spin: xe, Empty: H, Modal: Se, Input: $e, Popconfirm: ke, message: P } = window.QwenPaw.host.antd, _e = {
  release: { icon: "📦", cls: "gh-tag-purple" },
  commit: { icon: "📝", cls: "gh-tag-blue" },
  star_update: { icon: "⭐", cls: "gh-tag-warning" },
  repo_meta_update: { icon: "📌", cls: "" },
  trending_new: { icon: "🔥", cls: "gh-tag-accent" },
  refresh_error: { icon: "⚠️", cls: "gh-tag-warning" },
  collector_error: { icon: "❌", cls: "gh-tag-warning" }
};
function Ae() {
  const [a, d] = r.useState([]), [g, p] = r.useState([]), [c, v] = r.useState(!1), [h, w] = r.useState(!1), [f, S] = r.useState(""), i = r.useCallback(async () => {
    v(!0);
    try {
      const [e, b] = await Promise.all([
        k("/monitor/subscriptions"),
        k("/monitor/events?limit=50")
      ]);
      d(Array.isArray(e == null ? void 0 : e.subscriptions) ? e.subscriptions : []), p(Array.isArray(b == null ? void 0 : b.events) ? b.events : []);
    } catch (e) {
      console.error(e);
    } finally {
      v(!1);
    }
  }, []);
  r.useEffect(() => {
    i();
  }, [i]);
  const y = async () => {
    if (f.trim())
      try {
        await I(`/monitor/subscriptions?target=${encodeURIComponent(f)}`, {}), S(""), w(!1), P.success("订阅成功,正在拉取详情..."), setTimeout(i, 2e3);
      } catch {
        P.error("订阅失败");
      }
  }, $ = async (e) => {
    try {
      await ie(`/monitor/subscriptions/${e}`), P.success("已取消"), i();
    } catch {
      P.error("取消失败");
    }
  };
  return /* @__PURE__ */ r.createElement("div", { style: { padding: 16 } }, /* @__PURE__ */ r.createElement("div", { className: "gh-row", style: { justifyContent: "space-between", marginBottom: 16 } }, /* @__PURE__ */ r.createElement("h3", null, "📡 我的订阅 (", a.length, ")"), /* @__PURE__ */ r.createElement(J, { type: "primary", onClick: () => w(!0) }, "+ 添加订阅")), c ? /* @__PURE__ */ r.createElement(xe, null) : a.length === 0 ? /* @__PURE__ */ r.createElement(H, { description: "暂无订阅" }) : /* @__PURE__ */ r.createElement("table", { className: "gh-table", style: { marginBottom: 24 } }, /* @__PURE__ */ r.createElement("thead", null, /* @__PURE__ */ r.createElement("tr", null, /* @__PURE__ */ r.createElement("th", null, "仓库"), /* @__PURE__ */ r.createElement("th", null, "状态"), /* @__PURE__ */ r.createElement("th", null, "当前 Stars"), /* @__PURE__ */ r.createElement("th", null, "上次检查"), /* @__PURE__ */ r.createElement("th", { style: { width: 100 } }, "操作"))), /* @__PURE__ */ r.createElement("tbody", null, a.map((e) => /* @__PURE__ */ r.createElement("tr", { key: e.id }, /* @__PURE__ */ r.createElement("td", { style: { fontWeight: 500 } }, e.target), /* @__PURE__ */ r.createElement("td", null, e.enabled ? /* @__PURE__ */ r.createElement("span", { className: "gh-tag gh-tag-accent" }, "监控中") : /* @__PURE__ */ r.createElement("span", { className: "gh-tag" }, "已暂停")), /* @__PURE__ */ r.createElement("td", null, e.current_stars != null ? `⭐ ${A(e.current_stars)}` : "—"), /* @__PURE__ */ r.createElement("td", { style: { fontSize: "0.75rem", color: "var(--gh-text-tertiary)" } }, e.last_checked_at ? U(e.last_checked_at) : "未拉取"), /* @__PURE__ */ r.createElement("td", null, /* @__PURE__ */ r.createElement(ke, { title: "确认取消?", onConfirm: () => $(e.id) }, /* @__PURE__ */ r.createElement(J, { size: "small", danger: !0 }, "删除"))))))), /* @__PURE__ */ r.createElement("h3", { style: { marginBottom: 12 } }, "📊 监控动态 (", g.length, ")"), g.length === 0 ? /* @__PURE__ */ r.createElement(H, { description: "暂无动态" }) : /* @__PURE__ */ r.createElement("div", null, g.map((e, b) => {
    const m = _e[e.event_type] ?? { icon: "📌", cls: "" };
    return /* @__PURE__ */ r.createElement("div", { key: b, className: "gh-card", style: { marginBottom: 8 } }, /* @__PURE__ */ r.createElement("div", { className: "gh-row", style: { justifyContent: "space-between" } }, /* @__PURE__ */ r.createElement("div", { className: "gh-row" }, /* @__PURE__ */ r.createElement("span", { style: { fontWeight: 500 } }, e.repo_name), /* @__PURE__ */ r.createElement("span", { className: `gh-tag ${m.cls}` }, m.icon, " ", e.event_type)), /* @__PURE__ */ r.createElement("span", { style: { fontSize: "0.75rem", color: "var(--gh-text-tertiary)" } }, U(e.event_time))), /* @__PURE__ */ r.createElement("div", { style: { marginTop: 6 } }, e.title), e.body && /* @__PURE__ */ r.createElement("div", { style: { fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 } }, e.body));
  })), /* @__PURE__ */ r.createElement(Se, { title: "添加订阅", open: h, onOk: y, onCancel: () => w(!1) }, /* @__PURE__ */ r.createElement(
    $e,
    {
      placeholder: "owner/repo (例: facebook/react)",
      value: f,
      onChange: (e) => S(e.target.value),
      onPressEnter: y
    }
  )));
}
const t = window.QwenPaw.host.React, { Spin: Ce, Empty: Ne, Drawer: Te, Button: q } = window.QwenPaw.host.antd;
function Be() {
  const [a, d] = t.useState([]), [g, p] = t.useState(!1), [c, v] = t.useState(null), [h, w] = t.useState(!1), f = t.useCallback(async () => {
    p(!0);
    try {
      const i = await k("/reports?limit=50");
      d(Array.isArray(i == null ? void 0 : i.reports) ? i.reports : []);
    } catch {
      d([]);
    } finally {
      p(!1);
    }
  }, []);
  t.useEffect(() => {
    f();
  }, [f]);
  const S = (i) => {
    v(i), w(!0);
  };
  return /* @__PURE__ */ t.createElement("div", { style: { padding: 16 } }, /* @__PURE__ */ t.createElement("div", { className: "gh-row", style: { justifyContent: "space-between", marginBottom: 16 } }, /* @__PURE__ */ t.createElement("h3", null, "📊 分析报告 (", a.length, ")"), /* @__PURE__ */ t.createElement(q, { onClick: f }, "🔄 刷新")), g ? /* @__PURE__ */ t.createElement(Ce, null) : a.length === 0 ? /* @__PURE__ */ t.createElement(Ne, { description: "暂无报告" }) : /* @__PURE__ */ t.createElement("table", { className: "gh-table" }, /* @__PURE__ */ t.createElement("thead", null, /* @__PURE__ */ t.createElement("tr", null, /* @__PURE__ */ t.createElement("th", null, "日期"), /* @__PURE__ */ t.createElement("th", null, "类型"), /* @__PURE__ */ t.createElement("th", null, "来源"), /* @__PURE__ */ t.createElement("th", null, "概览"), /* @__PURE__ */ t.createElement("th", { style: { width: 80 } }, "操作"))), /* @__PURE__ */ t.createElement("tbody", null, a.map((i) => {
    var y, $;
    return /* @__PURE__ */ t.createElement("tr", { key: i.id }, /* @__PURE__ */ t.createElement("td", null, i.date), /* @__PURE__ */ t.createElement("td", null, /* @__PURE__ */ t.createElement("span", { className: "gh-tag gh-tag-blue" }, i.type)), /* @__PURE__ */ t.createElement("td", null, i.source === "llm" ? /* @__PURE__ */ t.createElement("span", { className: "gh-tag gh-tag-purple" }, "🤖 AI") : /* @__PURE__ */ t.createElement("span", { className: "gh-tag gh-tag-accent" }, "📝 手动")), /* @__PURE__ */ t.createElement("td", { style: { color: "var(--gh-text-secondary)", fontSize: "0.8rem" } }, (($ = (y = i.content) == null ? void 0 : y.overview) == null ? void 0 : $.slice(0, 80)) ?? "—"), /* @__PURE__ */ t.createElement("td", null, /* @__PURE__ */ t.createElement(q, { size: "small", onClick: () => S(i) }, "查看")));
  }))), /* @__PURE__ */ t.createElement(Te, { title: c ? `报告 - ${c.date}` : "", placement: "right", width: 560, open: h, onClose: () => w(!1) }, (c == null ? void 0 : c.content) && /* @__PURE__ */ t.createElement("div", null, c.content.overview && /* @__PURE__ */ t.createElement(t.Fragment, null, /* @__PURE__ */ t.createElement("h4", null, "📊 概览"), /* @__PURE__ */ t.createElement("p", { style: { color: "var(--gh-text-secondary)" } }, c.content.overview)), c.content.highlights && c.content.highlights.length > 0 && /* @__PURE__ */ t.createElement(t.Fragment, null, /* @__PURE__ */ t.createElement("h4", { style: { marginTop: 16 } }, "🔥 亮点项目"), c.content.highlights.map((i, y) => /* @__PURE__ */ t.createElement("div", { key: y, className: "gh-card", style: { marginBottom: 8 } }, /* @__PURE__ */ t.createElement("div", { style: { fontWeight: 500 } }, i.project), /* @__PURE__ */ t.createElement("div", { style: { fontSize: "0.8rem", color: "var(--gh-text-tertiary)", marginTop: 4 } }, i.insight)))), c.content.trends && c.content.trends.length > 0 && /* @__PURE__ */ t.createElement(t.Fragment, null, /* @__PURE__ */ t.createElement("h4", { style: { marginTop: 16 } }, "📈 趋势"), /* @__PURE__ */ t.createElement("ul", { style: { paddingLeft: 20 } }, c.content.trends.map((i, y) => /* @__PURE__ */ t.createElement("li", { key: y }, i)))), c.content.suggestions && c.content.suggestions.length > 0 && /* @__PURE__ */ t.createElement(t.Fragment, null, /* @__PURE__ */ t.createElement("h4", { style: { marginTop: 16 } }, "💡 建议"), /* @__PURE__ */ t.createElement("ul", { style: { paddingLeft: 20 } }, c.content.suggestions.map((i, y) => /* @__PURE__ */ t.createElement("li", { key: y }, i)))))));
}
const o = window.QwenPaw.host.React, { Switch: Re, InputNumber: Pe, Radio: D, Select: De, Button: K, message: _, Spin: ze } = window.QwenPaw.host.antd, Ie = [30, 60, 180, 360, 720, 1440], Le = [
  { value: "", label: "全部" },
  { value: "python", label: "Python" },
  { value: "go", label: "Go" },
  { value: "rust", label: "Rust" },
  { value: "typescript", label: "TypeScript" },
  { value: "javascript", label: "JavaScript" },
  { value: "java", label: "Java" },
  { value: "html", label: "HTML" }
];
function Fe() {
  const [a, d] = o.useState(!0), [g, p] = o.useState(null), [c, v] = o.useState(60), [h, w] = o.useState(!0), [f, S] = o.useState("daily"), [i, y] = o.useState([""]), [$, e] = o.useState(!1), [b, m] = o.useState(null), [E, te] = o.useState(
    null
  ), B = o.useCallback(async () => {
    d(!0);
    try {
      const s = await k("/settings");
      p(s), w(s.collect_enabled), v(s.collect_interval_min), S(s.collect_period), y(s.collect_languages);
    } catch {
      _.error("加载设置失败");
    } finally {
      d(!1);
    }
  }, []);
  o.useEffect(() => {
    B();
  }, [B]);
  const R = async (s = {}) => {
    const N = {
      collect_enabled: s.collect_enabled ?? h,
      collect_interval_min: s.collect_interval_min ?? c,
      collect_period: s.collect_period ?? f,
      collect_languages: s.collect_languages ?? i
    };
    try {
      await ge("/settings", N), _.success("已保存"), await B();
    } catch {
      _.error("保存失败");
    }
  }, ae = async (s) => {
    w(s), await R({ collect_enabled: s });
  }, M = async (s) => {
    s != null && (v(s), await R({ collect_interval_min: s }));
  }, ne = async (s) => {
    const N = s.target.value;
    S(N), await R({ collect_period: N });
  }, re = async (s) => {
    y(s), await R({ collect_languages: s });
  }, le = async () => {
    e(!0), m(null);
    try {
      const s = await I("/settings/trigger-collect", {});
      m(s.task_id), oe(s.task_id);
    } catch {
      _.error("触发失败"), e(!1);
    }
  }, oe = async (s) => {
    const N = Date.now(), L = async () => {
      var O;
      try {
        const C = await k(
          `/settings/trigger-collect/${s}`
        );
        C.status === "done" ? (te(C.result ?? null), e(!1), _.success(
          `采集完成: ${((O = C.result) == null ? void 0 : O.ok.length) ?? 0} 个语言成功`
        )) : C.status === "error" || C.status === "timeout" ? (e(!1), _.error(`采集${C.status === "timeout" ? "超时" : "失败"}`)) : Date.now() - N > 6 * 60 * 1e3 ? (e(!1), _.error("轮询超时")) : setTimeout(L, 3e3);
      } catch {
        e(!1), _.error("查状态失败");
      }
    };
    L();
  };
  return a || !g ? /* @__PURE__ */ o.createElement("div", { style: { padding: 32, textAlign: "center" } }, /* @__PURE__ */ o.createElement(ze, null)) : /* @__PURE__ */ o.createElement("div", { style: { padding: 24, maxWidth: 720 } }, /* @__PURE__ */ o.createElement("h2", { style: { marginBottom: 24 } }, "⚙️ 采集设置"), /* @__PURE__ */ o.createElement("section", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ o.createElement("h4", { style: { marginBottom: 12 } }, "启用采集"), /* @__PURE__ */ o.createElement(Re, { checked: h, onChange: ae }), /* @__PURE__ */ o.createElement("span", { className: "gh-text-secondary", style: { marginLeft: 12 } }, h ? "✅ 运行中" : "⏸ 已暂停")), /* @__PURE__ */ o.createElement("section", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ o.createElement("h4", { style: { marginBottom: 12 } }, "采集频率"), /* @__PURE__ */ o.createElement(
    Pe,
    {
      value: c,
      onChange: M,
      min: 5,
      max: 10080,
      addonAfter: "分钟"
    }
  ), /* @__PURE__ */ o.createElement(
    "div",
    {
      style: { marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }
    },
    Ie.map((s) => /* @__PURE__ */ o.createElement(
      "button",
      {
        key: s,
        className: `gh-button ${c === s ? "gh-button-primary" : ""}`,
        onClick: () => M(s)
      },
      s < 60 ? `${s}分` : s < 1440 ? `${s / 60}时` : `${s / 1440}天`
    ))
  )), /* @__PURE__ */ o.createElement("section", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ o.createElement("h4", { style: { marginBottom: 12 } }, "周期"), /* @__PURE__ */ o.createElement(
    D.Group,
    {
      value: f,
      onChange: ne,
      style: { display: "flex", gap: 8 }
    },
    /* @__PURE__ */ o.createElement(D, { value: "daily" }, "Daily"),
    /* @__PURE__ */ o.createElement(D, { value: "weekly" }, "Weekly"),
    /* @__PURE__ */ o.createElement(D, { value: "monthly" }, "Monthly")
  )), /* @__PURE__ */ o.createElement("section", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ o.createElement("h4", { style: { marginBottom: 12 } }, "抓取语言"), /* @__PURE__ */ o.createElement(
    De,
    {
      mode: "multiple",
      value: i,
      onChange: re,
      style: { width: "100%" },
      options: Le
    }
  ), /* @__PURE__ */ o.createElement(
    "p",
    {
      className: "gh-text-tertiary",
      style: { fontSize: "0.75rem", marginTop: 8 }
    },
    "留「全部」代表 github.com/trending 主页(不限定语言)"
  )), /* @__PURE__ */ o.createElement("section", { className: "gh-card", style: { marginBottom: 16 } }, /* @__PURE__ */ o.createElement("h4", { style: { marginBottom: 12 } }, "状态"), E ? /* @__PURE__ */ o.createElement(
    "div",
    {
      className: "gh-text-secondary",
      style: { fontSize: "0.85rem" }
    },
    "上次运行: ",
    E.date,
    " · ✅ ",
    E.ok.length,
    " 成功",
    E.errors.length > 0 && /* @__PURE__ */ o.createElement(
      "span",
      {
        className: "gh-tag gh-tag-warning",
        style: { marginLeft: 8 }
      },
      "❌ ",
      E.errors.length,
      " 失败"
    )
  ) : /* @__PURE__ */ o.createElement(
    "div",
    {
      className: "gh-text-tertiary",
      style: { fontSize: "0.85rem" }
    },
    "还没手动触发过采集"
  )), /* @__PURE__ */ o.createElement("div", { style: { display: "flex", gap: 12 } }, /* @__PURE__ */ o.createElement(
    K,
    {
      type: "primary",
      loading: $,
      onClick: le,
      disabled: !h
    },
    "🚀 立即采集一次"
  ), /* @__PURE__ */ o.createElement(K, { onClick: B }, "🔄 刷新状态")));
}
const u = "gh-trending-root", Me = `
.${u} {
  --gh-bg: #0A0D14;
  --gh-card: #171D2A;
  --gh-card-hover: #1E2538;
  --gh-elevated: #222A3E;
  --gh-border: #262F42;
  --gh-border-hover: #364059;
  --gh-text: #E4EAF0;
  --gh-text-secondary: #8892A8;
  --gh-text-tertiary: #5A6478;
  --gh-accent: #00D4AA;
  --gh-accent-hover: #00E8BA;
  --gh-accent-glow: rgba(0, 212, 170, 0.2);
  --gh-warning: #FFB800;
  --gh-danger: #FF4D6A;
  --gh-blue: #4A9EFF;
  --gh-purple: #8B5CF6;
  --gh-radius-sm: 6px;
  --gh-radius-md: 10px;
  --gh-radius-lg: 16px;
  --gh-font: 'DM Sans', -apple-system, system-ui, sans-serif;
  --gh-mono: 'JetBrains Mono', monospace;
  font-family: var(--gh-font);
  color: var(--gh-text);
}
.${u} *,
.${u} *::before,
.${u} *::after { box-sizing: border-box; }
.${u} .gh-card {
  background: var(--gh-card);
  border: 1px solid var(--gh-border);
  border-radius: var(--gh-radius-lg);
  padding: 16px;
  transition: border-color 0.15s;
}
.${u} .gh-card:hover { border-color: var(--gh-border-hover); }
.${u} .gh-text-secondary { color: var(--gh-text-secondary); }
.${u} .gh-text-tertiary { color: var(--gh-text-tertiary); }
.${u} .gh-accent { color: var(--gh-accent); }
.${u} .gh-row {
  display: flex; align-items: center; gap: 12px;
}
.${u} .gh-table { width: 100%; border-collapse: collapse; }
.${u} .gh-table th {
  text-align: left; padding: 10px 12px;
  font-size: 0.75rem; font-weight: 500;
  color: var(--gh-text-tertiary);
  background: var(--gh-elevated);
  border-bottom: 1px solid var(--gh-border);
}
.${u} .gh-table td {
  padding: 10px 12px; font-size: 0.85rem;
  border-bottom: 1px solid var(--gh-border);
  color: var(--gh-text);
}
.${u} .gh-table tr:hover td { background: var(--gh-card-hover); cursor: pointer; }
.${u} .gh-button {
  background: var(--gh-elevated);
  border: 1px solid var(--gh-border);
  color: var(--gh-text);
  padding: 6px 14px;
  border-radius: var(--gh-radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.${u} .gh-button:hover { border-color: var(--gh-accent); color: var(--gh-accent); }
.${u} .gh-button-primary {
  background: var(--gh-accent);
  border-color: var(--gh-accent);
  color: #0A0D14;
  font-weight: 600;
}
.${u} .gh-button-primary:hover { background: var(--gh-accent-hover); }
.${u} .gh-tag {
  display: inline-block; padding: 2px 8px;
  border-radius: 12px; font-size: 0.7rem;
  background: var(--gh-elevated);
  color: var(--gh-text-secondary);
  border: 1px solid var(--gh-border);
}
.${u} .gh-tag-accent { color: var(--gh-accent); border-color: var(--gh-accent); }
.${u} .gh-tag-warning { color: var(--gh-warning); border-color: var(--gh-warning); }
.${u} .gh-tag-purple { color: var(--gh-purple); border-color: var(--gh-purple); }
.${u} .gh-tag-blue { color: var(--gh-blue); border-color: var(--gh-blue); }
.${u} h1, h2, h3, h4, h5 { color: var(--gh-text); margin: 0; }
.${u} a { color: var(--gh-accent); }
`, Z = window.QwenPaw.host, x = Z.React, { Tabs: ee } = Z.antd, { TabPane: T } = ee;
function Oe() {
  const [a, d] = x.useState("trending");
  return /* @__PURE__ */ x.createElement("div", { className: u, style: { height: "100%" } }, /* @__PURE__ */ x.createElement("style", { dangerouslySetInnerHTML: { __html: Me } }), /* @__PURE__ */ x.createElement(
    ee,
    {
      activeKey: a,
      onChange: d,
      style: { height: "100%", padding: "0 16px" }
    },
    /* @__PURE__ */ x.createElement(T, { tab: "🔥 热榜", key: "trending" }, /* @__PURE__ */ x.createElement(pe, null)),
    /* @__PURE__ */ x.createElement(T, { tab: "📦 仓库", key: "repos" }, /* @__PURE__ */ x.createElement(we, null)),
    /* @__PURE__ */ x.createElement(T, { tab: "📡 订阅", key: "monitor" }, /* @__PURE__ */ x.createElement(Ae, null)),
    /* @__PURE__ */ x.createElement(T, { tab: "📊 报告", key: "reports" }, /* @__PURE__ */ x.createElement(Be, null)),
    /* @__PURE__ */ x.createElement(T, { tab: "⚙️ 设置", key: "settings" }, /* @__PURE__ */ x.createElement(Fe, null))
  ));
}
var Y, V;
(V = (Y = window.QwenPaw).registerRoutes) == null || V.call(Y, "github-trending", [
  {
    path: "/plugin/github-trending",
    component: Oe,
    label: "热榜",
    icon: "📊",
    priority: 10
  }
]);
