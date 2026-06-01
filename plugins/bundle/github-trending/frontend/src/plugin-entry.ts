/// <reference types="../../../console/src/global" />

(function () {
  const host = window.QwenPaw.host;
  const React = host.React;
  const antd = host.antd;
  const {
    Button, Card, Space, Typography, List, Tag, Select, Table,
    Modal, message, Spin, DatePicker, Row, Col, Statistic,
    Divider, Tabs, Input, Badge, Empty, Popconfirm, Descriptions,
    Drawer, Steps, Progress, Tooltip, Alert
  } = antd;
  const { Title, Paragraph, Text, ParagraphProps } = Typography;
  const { Option } = Select;
  const { RangePicker } = DatePicker;
  const { TabPane } = Tabs;
  const { Search } = Input;
  const getApiUrl = host.getApiUrl;

  const API_BASE = "http://localhost:7901";

  // ── API 封装 ──

  async function apiGet(path: string) {
    const res = await fetch(`${API_BASE}${path}`);
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  async function apiPost(path: string, body: any) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  async function apiDelete(path: string) {
    const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  // ── 工具函数 ──

  function formatNumber(num: number): string {
    if (num >= 1000) {
      return (num / 1000).toFixed(1) + "k";
    }
    return num.toString();
  }

  function formatStarsDelta(delta: number): string {
    if (delta > 0) return "+" + formatNumber(delta) + " ↑";
    if (delta < 0) return formatNumber(delta) + " ↓";
    return "—";
  }

  function getTimeAgo(time: string): string {
    const now = new Date();
    const date = new Date(time);
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diff < 60) return "刚刚";
    if (diff < 3600) return Math.floor(diff / 60) + "分钟前";
    if (diff < 86400) return Math.floor(diff / 3600) + "小时前";
    return Math.floor(diff / 86400) + "天前";
  }

  // ── 通用组件 ──

  function StatCard({ title, value, suffix, color }: any) {
    return React.createElement(Card, { size: "small", style: { textAlign: "center" } },
      React.createElement(Title, { level: 4, style: { margin: 0, color: color || "#1890ff" } }, value),
      suffix && React.createElement(Text, { type: "secondary" }, suffix),
      !suffix && React.createElement(Text, { type: "secondary" }, title)
    );
  }

  function RepoCard({ repo, onClick }: any) {
    return React.createElement(Card, {
      size: "small",
      hoverable: true,
      onClick: () => onClick?.(repo),
      style: { cursor: "pointer", marginBottom: 8 }
    },
      React.createElement(Space, { direction: "vertical", style: { width: "100%" }, size: "small" },
        React.createElement(Space, { style: { width: "100%", justifyContent: "space-between" } },
          React.createElement(Tag, { color: "blue" }, repo.language || "—"),
          React.createElement(Space, null,
            React.createElement(Text, null, "⭐ " + formatNumber(repo.stars)),
            repo.stars_delta > 0 && React.createElement(Text, { type: "success" }, "+" + formatNumber(repo.stars_delta)),
            repo.stars_delta === 0 && React.createElement(Text, { type: "secondary" }, "—"),
            React.createElement(Text, null, " 🍴 " + formatNumber(repo.forks))
          )
        ),
        React.createElement(Title, { level: 5, style: { margin: 0 } },
          React.createElement("a", { href: repo.url, target: "_blank", onClick: e => e.stopPropagation() }, repo.full_name)
        ),
        repo.description && React.createElement(Paragraph, { ellipsis: { rows: 2 }, type: "secondary" }, repo.description)
      )
    );
  }

  // ── 热榜页面 ──

  function TrendingPage() {
    const [loading, setLoading] = React.useState(false);
    const [dates, setDates] = React.useState<string[]>([]);
    const [selectedDate, setSelectedDate] = React.useState<string | null>(null);
    const [data, setData] = React.useState<any>(null);
    const [sortBy, setSortBy] = React.useState("stars");
    const [language, setLanguage] = React.useState("all");

    // 加载日期列表
    React.useEffect(() => {
      apiGet("/trending/dates?language=" + language)
        .then(setDates)
        .catch(console.error);
    }, [language]);

    // 加载数据
    React.useEffect(() => {
      if (!selectedDate) return;
      setLoading(true);
      apiGet("/trending/daily?date=" + selectedDate + "&language=" + language)
        .then(setData)
        .catch(() => setData(null))
        .finally(() => setLoading(false));
    }, [selectedDate, language]);

    // 默认选中最新日期
    React.useEffect(() => {
      if (dates.length > 0 && !selectedDate) {
        setSelectedDate(dates[0]);
      }
    }, [dates]);

    // 排序
    const sortedItems = React.useMemo(() => {
      if (!data?.items) return [];
      const items = [...data.items];
      switch (sortBy) {
        case "stars": return items.sort((a, b) => b.stars - a.stars);
        case "delta": return items.sort((a, b) => (b.stars_delta || 0) - (a.stars_delta || 0));
        case "forks": return items.sort((a, b) => b.forks - a.forks);
        default: return items;
      }
    }, [data, sortBy]);

    // 下载
    const handleDownload = (format: "csv" | "json") => {
      if (!data) return;
      let content: string;
      let filename: string;
      let mimeType: string;

      if (format === "json") {
        content = JSON.stringify(data.items, null, 2);
        filename = `trending-${data.date}.json`;
        mimeType = "application/json";
      } else {
        const header = "rank,name,full_name,description,language,stars,stars_delta,forks,url\n";
        const rows = data.items.map((item: any) =>
          `${item.rank},"${item.name}","${item.full_name}","${item.description || ""}","${item.language || ""}",${item.stars},${item.stars_delta || 0},${item.forks || 0},"${item.url}"`
        ).join("\n");
        content = header + rows;
        filename = `trending-${data.date}.csv`;
        mimeType = "text/csv";
      }

      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      message.success("下载成功");
    };

    return React.createElement("div", { style: { padding: 16 } },
      // 头部
      React.createElement(Space, { style: { marginBottom: 16 }, wrap: true },
        React.createElement(Select, {
          value: selectedDate,
          onChange: setSelectedDate,
          style: { width: 200 },
          showSearch: true,
          filterOption: (input, option) =>
            (option?.children as any)?.props?.title?.toLowerCase()?.includes(input.toLowerCase())
        },
          dates.map(date => {
            const isToday = date === new Date().toISOString().split("T")[0];
            return React.createElement(Option, { key: date, value: date, title: date },
              isToday ? date + " (今日)" : date
            );
          })
        ),
        React.createElement(Select, {
          value: language,
          onChange: setLanguage,
          style: { width: 120 }
        },
          React.createElement(Option, { value: "all" }, "全部语言"),
          React.createElement(Option, { value: "python" }, "Python"),
          React.createElement(Option, { value: "javascript" }, "JavaScript"),
          React.createElement(Option, { value: "typescript" }, "TypeScript"),
          React.createElement(Option, { value: "rust" }, "Rust"),
          React.createElement(Option, { value: "go" }, "Go"),
          React.createElement(Option, { value: "java" }, "Java"),
          React.createElement(Option, { value: "html" }, "HTML")
        ),
        React.createElement(Space, null,
          React.createElement(Text, { type: "secondary" }, "排序:"),
          React.createElement(Select, {
            value: sortBy,
            onChange: setSortBy,
            style: { width: 120 }
          },
            React.createElement(Option, { value: "stars" }, "⭐ 总星数"),
            React.createElement(Option, { value: "delta" }, "📈 今日涨幅"),
            React.createElement(Option, { value: "forks" }, "🍴 Fork数")
          )
        ),
        React.createElement(Space, null,
          React.createElement(Button, { onClick: () => handleDownload("csv") }, "📄 CSV"),
          React.createElement(Button, { onClick: () => handleDownload("json") }, "📋 JSON")
        )
      ),

      // 统计
      data && React.createElement(Row, { gutter: 16, style: { marginBottom: 16 } },
        React.createElement(Col, { span: 6 },
          React.createElement(StatCard, { title: "项目总数", value: data.total_count })
        ),
        React.createElement(Col, { span: 6 },
          React.createElement(StatCard, { title: "采集次数", value: data.updated_count, color: "#52c41a" })
        ),
        React.createElement(Col, { span: 6 },
          React.createElement(StatCard, { title: "日期", value: data.date, color: "#722ed1" })
        )
      ),

      // 列表
      loading && React.createElement(Spin, { style: { display: "block", textAlign: "center", marginTop: 50 } }),
      !loading && !data && React.createElement(Empty, { description: "暂无数据", style: { marginTop: 50 } }),
      !loading && data && React.createElement(List, {
        dataSource: sortedItems,
        renderItem: (item: any) => React.createElement(List.Item, { style: { padding: "12px 0" } },
          React.createElement(Card, {
            size: "small",
            style: { width: "100%" },
            hoverable: true
          },
            React.createElement(Space, { direction: "vertical", style: { width: "100%" }, size: "small" },
              React.createElement(Space, { style: { width: "100%", justifyContent: "space-between" } },
                React.createElement(Space, null,
                  React.createElement(Tag, { color: "gold" }, "#" + item.rank),
                  React.createElement(Tag, { color: "blue" }, item.language || "—")
                ),
                React.createElement(Space, null,
                  React.createElement(Text, null, "⭐ " + formatNumber(item.stars)),
                  item.stars_delta > 0 && React.createElement(Tag, { color: "green" }, "+" + formatNumber(item.stars_delta)),
                  React.createElement(Text, null, " 🍴 " + formatNumber(item.forks || 0))
                )
              ),
              React.createElement(Title, { level: 5, style: { margin: 0 } },
                React.createElement("a", { href: item.url, target: "_blank" }, item.full_name)
              ),
              item.description && React.createElement(Paragraph, { ellipsis: { rows: 2 }, type: "secondary" }, item.description)
            )
          )
        )
      })
    );
  }

  // ── 仓库页面 ──

  function ReposPage() {
    const [loading, setLoading] = React.useState(false);
    const [results, setResults] = React.useState<any[]>([]);
    const [selectedRepo, setSelectedRepo] = React.useState<any>(null);
    const [trendData, setTrendData] = React.useState<any[]>([]);
    const [drawerVisible, setDrawerVisible] = React.useState(false);

    const handleSearch = (value: string) => {
      if (!value.trim()) return;
      setLoading(true);
      apiGet("/repos/search?keyword=" + encodeURIComponent(value))
        .then(setResults)
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    };

    const handleViewRepo = (repo: any) => {
      setSelectedRepo(repo);
      setDrawerVisible(true);
      apiGet("/repos/" + encodeURIComponent(repo.full_name) + "/trend")
        .then(setTrendData)
        .catch(() => setTrendData([]));
    };

    return React.createElement("div", { style: { padding: 16 } },
      React.createElement(Search, {
        placeholder: "搜索项目名...",
        enterButton: "搜索",
        size: "large",
        loading: loading,
        onSearch: handleSearch,
        style: { marginBottom: 16 }
      }),
      React.createElement(List, {
        dataSource: results,
        locale: { emptyText: "输入项目名搜索" },
        renderItem: (repo: any) => React.createElement(List.Item, null,
          React.createElement(Card, {
            size: "small",
            hoverable: true,
            onClick: () => handleViewRepo(repo),
            style: { width: "100%", cursor: "pointer" }
          },
            React.createElement(Space, { direction: "vertical", style: { width: "100%" }, size: "small" },
              React.createElement(Space, { style: { width: "100%", justifyContent: "space-between" } },
                React.createElement(Title, { level: 5, style: { margin: 0 } }, repo.full_name),
                React.createElement(Space, null,
                  React.createElement(Tag, { color: "blue" }, repo.language || "—"),
                  React.createElement(Text, null, "⭐ " + formatNumber(repo.stars)),
                  React.createElement(Text, null, " 上榜 " + (repo.appearances || 0) + " 次")
                )
              ),
              repo.description && React.createElement(Paragraph, { ellipsis: { rows: 2 }, type: "secondary" }, repo.description)
            )
          )
        )
      }),

      // 详情抽屉
      React.createElement(Drawer, {
        title: selectedRepo?.full_name,
        placement: "right",
        width: 500,
        open: drawerVisible,
        onClose: () => setDrawerVisible(false)
      },
        selectedRepo && React.createElement(Descriptions, { column: 1, bordered: true, size: "small" },
          React.createElement(Descriptions.Item, { label: "Stars" }, formatNumber(selectedRepo.stars)),
          React.createElement(Descriptions.Item, { label: "Forks" }, formatNumber(selectedRepo.forks)),
          React.createElement(Descriptions.Item, { label: "语言" }, selectedRepo.language || "—"),
          React.createElement(Descriptions.Item, { label: "首次上榜" }, selectedRepo.first_seen || "—"),
          React.createElement(Descriptions.Item, { label: "最近上榜" }, selectedRepo.last_seen || "—"),
          React.createElement(Descriptions.Item, { label: "上榜次数" }, selectedRepo.appearances || 0),
          React.createElement(Descriptions.Item, { label: "链接" },
            React.createElement("a", { href: selectedRepo.url, target: "_blank" }, "打开 GitHub")
          )
        ),
        React.createElement(Title, { level: 5, style: { marginTop: 24 } }, "趋势数据"),
        trendData.length === 0 && React.createElement(Text, { type: "secondary" }, "暂无趋势数据"),
        React.createElement(List, {
          dataSource: trendData.slice(0, 10),
          renderItem: (item: any) => React.createElement(List.Item, null,
            React.createElement(Space, null,
              React.createElement(Tag, null, item.date),
              React.createElement(Text, null, "#" + item.rank),
              React.createElement(Text, null, "⭐ " + formatNumber(item.stars)),
              item.stars_delta > 0 && React.createElement(Tag, { color: "green" }, "+" + formatNumber(item.stars_delta))
            )
          )
        })
      )
    );
  }

  // ── 订阅监控页面 ──

  function MonitorPage() {
    const [subscriptions, setSubscriptions] = React.useState<any[]>([]);
    const [events, setEvents] = React.useState<any[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [addModalVisible, setAddModalVisible] = React.useState(false);
    const [newRepo, setNewRepo] = React.useState("");

    const loadData = React.useCallback(() => {
      setLoading(true);
      Promise.all([
        apiGet("/monitor/subscriptions"),
        apiGet("/monitor/events?limit=50")
      ])
        .then(([subs, evts]) => {
          setSubscriptions(subs);
          setEvents(evts);
        })
        .catch(console.error)
        .finally(() => setLoading(false));
    }, []);

    React.useEffect(() => {
      loadData();
    }, [loadData]);

    const handleAdd = async () => {
      if (!newRepo.trim()) return;
      try {
        await apiPost("/monitor/subscriptions?target=" + encodeURIComponent(newRepo), {});
        setNewRepo("");
        setAddModalVisible(false);
        loadData();
        message.success("订阅成功");
      } catch (e) {
        message.error("订阅失败");
      }
    };

    const handleDelete = async (id: number) => {
      try {
        await apiDelete("/monitor/subscriptions/" + id);
        loadData();
        message.success("已取消订阅");
      } catch (e) {
        message.error("取消失败");
      }
    };

    const getEventIcon = (type: string) => {
      switch (type) {
        case "release": return "📦";
        case "commit": return "📝";
        case "star_update": return "⭐";
        case "issue": return "❓";
        default: return "📌";
      }
    };

    const getEventColor = (type: string) => {
      switch (type) {
        case "release": return "purple";
        case "commit": return "blue";
        case "star_update": return "gold";
        case "issue": return "cyan";
        default: return "default";
      }
    };

    return React.createElement("div", { style: { padding: 16 } },
      React.createElement(Space, { style: { marginBottom: 16, width: "100%", justifyContent: "space-between" } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "我的订阅"),
        React.createElement(Button, { type: "primary", onClick: () => setAddModalVisible(true) }, "+ 添加订阅")
      ),

      // 订阅列表
      React.createElement(Card, { title: "订阅列表", size: "small", style: { marginBottom: 16 } },
        subscriptions.length === 0
          ? React.createElement(Empty, { description: "暂无订阅", image: Empty.PRESENTED_IMAGE_SIMPLE })
          : React.createElement(List, {
            size: "small",
            dataSource: subscriptions,
            renderItem: (sub: any) => React.createElement(List.Item, {
              actions: [
                React.createElement(Popconfirm, {
                  title: "确认取消订阅?",
                  onConfirm: () => handleDelete(sub.id),
                  children: React.createElement(Button, { size: "small", danger: true }, "删除")
                })
              ]
            },
              React.createElement(Space, null,
                React.createElement(Text, null, "💾 " + sub.target),
                sub.enabled
                  ? React.createElement(Tag, { color: "green" }, "监控中")
                  : React.createElement(Tag, { color: "default" }, "已暂停")
              )
            )
          })
      ),

      // 监控动态
      React.createElement(Card, { title: "监控动态", size: "small" },
        events.length === 0
          ? React.createElement(Empty, { description: "暂无动态", image: Empty.PRESENTED_IMAGE_SIMPLE })
          : React.createElement(List, {
            size: "small",
            dataSource: events,
            renderItem: (evt: any) => React.createElement(List.Item, null,
              React.createElement(Card, { size: "small", style: { width: "100%" }, bodyStyle: { padding: 12 } },
                React.createElement(Space, { direction: "vertical", size: "small", style: { width: "100%" } },
                  React.createElement(Space, { style: { width: "100%", justifyContent: "space-between" } },
                    React.createElement(Space, null,
                      React.createElement(Text, { strong: true }, "💾 " + evt.repo_name),
                      React.createElement(Tag, { color: getEventColor(evt.event_type) }, getEventIcon(evt.event_type) + " " + evt.event_type)
                    ),
                    React.createElement(Text, { type: "secondary", size: "small" }, getTimeAgo(evt.event_time))
                  ),
                  React.createElement(Text, null, evt.title),
                  evt.body && React.createElement(Paragraph, { type: "secondary", ellipsis: { rows: 2 }, style: { margin: 0 } }, evt.body),
                  evt.stars > 0 && React.createElement(Text, { type: "secondary", size: "small" }, "当前: ⭐ " + formatNumber(evt.stars))
                )
              )
            )
          })
      ),

      // 添加订阅弹窗
      React.createElement(Modal, {
        title: "添加订阅",
        open: addModalVisible,
        onOk: handleAdd,
        onCancel: () => setAddModalVisible(false)
      },
        React.createElement(Input, {
          placeholder: "owner/repo，例如: facebook/react",
          value: newRepo,
          onChange: e => setNewRepo(e.target.value)
        })
      )
    );
  }

  // ── 分析报告页面 ──

  function ReportsPage() {
    const [reports, setReports] = React.useState<any[]>([]);
    const [selectedReport, setSelectedReport] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(false);
    const [drawerVisible, setDrawerVisible] = React.useState(false);

    const loadReports = React.useCallback(() => {
      setLoading(true);
      apiGet("/reports")
        .then(setReports)
        .catch(() => setReports([]))
        .finally(() => setLoading(false));
    }, []);

    React.useEffect(() => {
      loadReports();
    }, [loadReports]);

    const handleView = (report: any) => {
      setSelectedReport(report);
      setDrawerVisible(true);
    };

    return React.createElement("div", { style: { padding: 16 } },
      React.createElement(Space, { style: { marginBottom: 16, width: "100%", justifyContent: "space-between" } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "分析报告"),
        React.createElement(Button, { onClick: loadReports }, "🔄 刷新")
      ),

      React.createElement(List, {
        loading: loading,
        dataSource: reports,
        locale: { emptyText: "暂无报告" },
        renderItem: (report: any) => React.createElement(List.Item, {
          actions: [
            React.createElement(Button, { size: "small", type: "link", onClick: () => handleView(report) }, "查看")
          ]
        },
          React.createElement(Card, { size: "small", style: { width: "100%" } },
            React.createElement(Space, { direction: "vertical", style: { width: "100%" }, size: "small" },
              React.createElement(Space, null,
                React.createElement(Tag, { color: "blue" }, report.type),
                React.createElement(Tag, { color: report.source === "llm" ? "purple" : "green" }, report.source === "llm" ? "🤖 AI" : "📝 手动"),
                React.createElement(Text, { type: "secondary" }, report.date)
              ),
              report.content?.overview && React.createElement(Paragraph, { ellipsis: { rows: 2 }, type: "secondary" }, report.content.overview)
            )
          )
        )
      }),

      // 报告详情抽屉
      React.createElement(Drawer, {
        title: "分析报告 - " + (selectedReport?.date || ""),
        placement: "right",
        width: 600,
        open: drawerVisible,
        onClose: () => setDrawerVisible(false)
      },
        selectedReport && React.createElement("div", null,
          selectedReport.content?.overview && React.createElement(React.Fragment, null,
            React.createElement(Title, { level: 5 }, "📊 概览"),
            React.createElement(Paragraph, null, selectedReport.content.overview),
            React.createElement(Divider, null)
          ),

          selectedReport.content?.highlights && React.createElement(React.Fragment, null,
            React.createElement(Title, { level: 5 }, "🔥 亮点项目"),
            React.createElement(List, {
              size: "small",
              dataSource: selectedReport.content.highlights,
              renderItem: (item: any) => React.createElement(List.Item, null,
                React.createElement(Space, { direction: "vertical", size: "small" },
                  React.createElement(Text, { strong: true }, item.project),
                  React.createElement(Text, { type: "secondary" }, item.insight)
                )
              )
            }),
            React.createElement(Divider, null)
          ),

          selectedReport.content?.trends && React.createElement(React.Fragment, null,
            React.createElement(Title, { level: 5 }, "📈 趋势发现"),
            React.createElement(List, {
              size: "small",
              dataSource: selectedReport.content.trends,
              renderItem: (trend: string) => React.createElement(List.Item, null,
                React.createElement(Text, null, "• " + trend)
              )
            }),
            React.createElement(Divider, null)
          ),

          selectedReport.content?.suggestions && React.createElement(React.Fragment, null,
            React.createElement(Title, { level: 5 }, "💡 建议"),
            React.createElement(List, {
              size: "small",
              dataSource: selectedReport.content.suggestions,
              renderItem: (sug: string) => React.createElement(List.Item, null,
                React.createElement(Text, null, "• " + sug)
              )
            })
          )
        )
      )
    );
  }

  // ── 主应用 ──

  function App() {
    const [activeTab, setActiveTab] = React.useState("trending");

    return React.createElement("div", { style: { height: "100%", display: "flex", flexDirection: "column" } },
      React.createElement(Tabs, {
        activeKey: activeTab,
        onChange: setActiveTab,
        style: { flex: 1, display: "flex", flexDirection: "column" } as any,
        tabBarStyle: { padding: "0 16px", margin: 0 }
      },
        React.createElement(TabPane, { tab: "🔥 热榜", key: "trending" },
          React.createElement(TrendingPage)
        ),
        React.createElement(TabPane, { tab: "💾 仓库", key: "repos" },
          React.createElement(ReposPage)
        ),
        React.createElement(TabPane, { tab: "📡 订阅", key: "monitor" },
          React.createElement(MonitorPage)
        ),
        React.createElement(TabPane, { tab: "📊 分析", key: "reports" },
          React.createElement(ReportsPage)
        )
      )
    );
  }

  // ── 注册路由 ──

  window.QwenPaw.registerRoutes?.("github-trending", [{
    path: "/plugin/github-trending",
    component: App,
    label: "热榜",
    icon: "📊",
    priority: 10,
  }]);
})();
