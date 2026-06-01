(function () {
  // Host: prefer QwenPaw.host (always populated) over window.* (tree-shaken in prod)
  const host = (window as any).QwenPaw?.host;
  const React = host?.React || (window as any).React;
  const antd = host?.antd || (window as any).antd;

  const {
    Card, Row, Col, Statistic, Select, DatePicker, Table, Button,
    Space, Spin, message, Tabs, Modal, Form, InputNumber, Switch,
    Divider, Popconfirm, Typography, Progress,
  } = antd;

  const { RangePicker } = DatePicker;
  const { Text } = Typography;
  const { Option } = Select;

  // 走宿主 host.getApiUrl:它已经会拼 /api 前缀。
  // 调用方写 /api/metrics/current,我们剥掉 /api 再交给 getApiUrl,避免 /api/api/... 404。
  const buildUrl = (url: string): string => {
    const stripped = url.replace(/^\/api/, "");
    if (host?.getApiUrl) return host.getApiUrl(stripped);
    return url;
  };

  async function api(method: string, url: string, body?: any) {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = host?.getApiToken ? host.getApiToken() : null;
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const opts: RequestInit = {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    };
    const res = await fetch(buildUrl(url), opts);
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  }

  // ============ Simple Bar Chart Component ============
  function BarChart({ data, color }: { data: number[]; color: string }) {
    if (!data || data.length === 0) return <Text>暂无数据</Text>;
    const max = Math.max(...data, 1);
    return (
      <div style={{ height: 120, display: "flex", alignItems: "flex-end", gap: 2 }}>
        {data.slice(-30).map((v, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              height: `${Math.max((v / max) * 100, 2)}%`,
              backgroundColor: color,
              minWidth: 3,
              borderRadius: "2px 2px 0 0",
            }}
            title={v.toFixed(1)}
          />
        ))}
      </div>
    );
  }

  // ============ Monitor Page ============
  function MonitorPage() {
    const [loading, setLoading] = React.useState(true);
    const [currentMetrics, setCurrentMetrics] = React.useState<any>(null);
    const [trendData, setTrendData] = React.useState<any>({});
    const [processType, setProcessType] = React.useState("cpu");
    const [processTop, setProcessTop] = React.useState<any[]>([]);
    const [viewMode, setViewMode] = React.useState<"chart" | "list">("chart");

    const fetchCurrent = React.useCallback(async () => {
      try {
        const data = await api("GET", "/api/metrics/current");
        setCurrentMetrics(data);
      } catch (e) {
        console.error(e);
      }
    }, []);

    const fetchTrends = React.useCallback(async (types: string[]) => {
      const results: any = {};
      for (const t of types) {
        try {
          const data = await api("GET", `/api/metrics/trend/${t}?limit=100`);
          results[t] = (data.data || []).reverse();
        } catch (e) {
          console.error(e);
        }
      }
      setTrendData(results);
    }, []);

    const fetchProcessTop = React.useCallback(async () => {
      try {
        const params = new URLSearchParams();
        params.set("type", processType);
        params.set("limit", "20");
        const data = await api("GET", `/api/metrics/process/top?${params}`);
        setProcessTop(data.data || []);
      } catch (e) {
        console.error(e);
      }
    }, [processType]);

    React.useEffect(() => {
      const init = async () => {
        setLoading(true);
        await fetchCurrent();
        await fetchTrends(["cpu", "memory", "load"]);
        setLoading(false);
      };
      init();
      const interval = setInterval(async () => {
        await fetchCurrent();
      }, 5000);
      return () => clearInterval(interval);
    }, [fetchCurrent, fetchTrends]);

    React.useEffect(() => {
      fetchProcessTop();
    }, [fetchProcessTop]);

    if (loading) return <Spin tip="加载中..." />;
    if (!currentMetrics) return <Card><Text>无法加载监控数据，请检查后端服务。</Text></Card>;

    const cpuValues = (trendData.cpu || []).map((d: any) => d.value);
    const memValues = (trendData.memory || []).map((d: any) => d.value);
    const loadValues = (trendData.load || []).map((d: any) => d.value);

    return (
      <div style={{ padding: 16 }}>
        {/* Stats Cards */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="CPU 使用率" value={currentMetrics.cpu?.percent || 0} suffix="%" precision={1} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="内存使用率" value={currentMetrics.memory?.percent || 0} suffix="%" precision={1} />
              <Text type="secondary" style={{ fontSize: 12 }}>
                {currentMetrics.memory?.used || 0} / {currentMetrics.memory?.total || 0} GB
              </Text>
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="系统负载 (1min)" value={currentMetrics.load?.["1min"] || 0} precision={2} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="文件句柄" value={currentMetrics.handles?.total || 0} />
            </Card>
          </Col>
          <Col span={4}>
            <Card size="small" hoverable>
              <Statistic title="进程数" value={currentMetrics.handles?.processes || 0} />
            </Card>
          </Col>
        </Row>

        {/* View Toggle */}
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Text>视图:</Text>
            <Button.Group>
              <Button type={viewMode === "chart" ? "primary" : "default"} onClick={() => setViewMode("chart")}>图表</Button>
              <Button type={viewMode === "list" ? "primary" : "default"} onClick={() => setViewMode("list")}>列表</Button>
            </Button.Group>
            <Button onClick={() => fetchTrends(["cpu", "memory", "load"])}>刷新趋势</Button>
          </Space>
        </div>

        {/* Trend Charts */}
        {viewMode === "chart" && (
          <Card title="趋势监控" style={{ marginBottom: 16 }}>
            <Row gutter={16}>
              <Col span={8}>
                <Text strong>CPU 使用率</Text>
                <BarChart data={cpuValues} color="#1890ff" />
              </Col>
              <Col span={8}>
                <Text strong>内存使用率</Text>
                <BarChart data={memValues} color="#52c41a" />
              </Col>
              <Col span={8}>
                <Text strong>系统负载</Text>
                <BarChart data={loadValues} color="#faad14" />
              </Col>
            </Row>
          </Card>
        )}

        {/* List View */}
        {viewMode === "list" && (
          <Card title="指标列表" style={{ marginBottom: 16 }}>
            <Table
              dataSource={(trendData.cpu || []).map((item: any, idx: number) => ({
                key: idx,
                time: item.timestamp,
                metric: "CPU",
                value: item.value,
                unit: item.unit,
              }))}
              columns={[
                { title: "时间", dataIndex: "time", key: "time", width: 180 },
                { title: "指标", dataIndex: "metric", key: "metric", width: 80 },
                { title: "值", dataIndex: "value", key: "value" },
                { title: "单位", dataIndex: "unit", key: "unit", width: 60 },
              ]}
              pagination={{ pageSize: 10 }}
              size="small"
            />
          </Card>
        )}

        {/* Process Top N */}
        <Card title="进程排名">
          <Space style={{ marginBottom: 16 }}>
            <Text>指标:</Text>
            <Select value={processType} onChange={setProcessType} style={{ width: 120 }}>
              <Option value="cpu">CPU</Option>
              <Option value="memory">内存</Option>
              <Option value="handle">句柄</Option>
            </Select>
            <Button onClick={fetchProcessTop}>刷新</Button>
          </Space>

          <Table
            dataSource={processTop.map((item: any, idx: number) => ({
              key: idx,
              rank: idx + 1,
              name: item.name || "-",
              pid: item.pid || "-",
              avg_value: item.avg_value?.toFixed(2) || "-",
              max_value: item.max_value?.toFixed(2) || "-",
            }))}
            columns={[
              { title: "排名", dataIndex: "rank", key: "rank", width: 60 },
              { title: "进程名", dataIndex: "name", key: "name" },
              { title: "PID", dataIndex: "pid", key: "pid", width: 80 },
              { title: "平均值", dataIndex: "avg_value", key: "avg_value" },
              { title: "最大值", dataIndex: "max_value", key: "max_value" },
            ]}
            pagination={{ pageSize: 20 }}
            size="small"
          />
        </Card>
      </div>
    );
  }

  // ============ Config Page ============
  function ConfigPage() {
    const [config, setConfig] = React.useState<any>(null);
    const [stats, setStats] = React.useState<any>(null);
    const [saving, setSaving] = React.useState(false);
    const [formData, setFormData] = React.useState<any>({});

    React.useEffect(() => {
      const load = async () => {
        try {
          const [cfg, st] = await Promise.all([
            api("GET", "/api/config"),
            api("GET", "/api/metrics/stats"),
          ]);
          setConfig(cfg);
          setStats(st);
          setFormData(cfg);
        } catch (e) {
          console.error(e);
        }
      };
      load();
    }, []);

    const handleSave = async () => {
      setSaving(true);
      try {
        await api("PUT", "/api/config", formData);
        message.success("配置已保存");
      } catch (e: any) {
        message.error("保存失败: " + e.message);
      }
      setSaving(false);
    };

    const handleCleanup = async () => {
      try {
        const result = await api("POST", "/api/metrics/cleanup", {});
        message.success(`已清理: 系统指标 ${result.metrics_deleted || 0} 条, 进程指标 ${result.processes_deleted || 0} 条`);
        const st = await api("GET", "/api/metrics/stats");
        setStats(st);
      } catch (e: any) {
        message.error("清理失败: " + e.message);
      }
    };

    if (!config) return <Spin tip="加载配置..." />;

    return (
      <div style={{ padding: 16 }}>
        <Card title="系统监控设置" style={{ marginBottom: 16 }}>
          <Form layout="vertical">
            <Form.Item label="采集频率（秒）">
              <InputNumber
                value={formData.interval || 5}
                min={1}
                max={3600}
                onChange={(v: number) => setFormData({ ...formData, interval: v })}
              />
            </Form.Item>

            <Divider>指标开关</Divider>

            {["cpu", "memory", "disk", "handle", "load", "process"].map((metric) => (
              <Form.Item key={metric} label={metric.toUpperCase()}>
                <Switch
                  checked={formData.enabled_metrics?.[metric] ?? true}
                  onChange={(checked: boolean) => setFormData({
                    ...formData,
                    enabled_metrics: { ...formData.enabled_metrics, [metric]: checked }
                  })}
                />
              </Form.Item>
            ))}

            <Form.Item label="数据保留天数">
              <InputNumber
                value={formData.retention_days || 7}
                min={1}
                max={365}
                onChange={(v: number) => setFormData({ ...formData, retention_days: v })}
              />
            </Form.Item>

            <Button type="primary" onClick={handleSave} loading={saving}>
              保存配置
            </Button>
          </Form>
        </Card>

        <Card title="数据管理">
          <p>系统指标记录: {stats?.metrics_count || 0} 条</p>
          <p>进程指标记录: {stats?.processes_count || 0} 条</p>
          <p>最早记录: {stats?.earliest || "无"}</p>
          <p>最新记录: {stats?.latest || "无"}</p>

          <Space style={{ marginTop: 16 }}>
            <Popconfirm
              title="确认清理所有历史数据?"
              onConfirm={handleCleanup}
              okText="确认"
              cancelText="取消"
            >
              <Button danger>立即清理</Button>
            </Popconfirm>
          </Space>
        </Card>
      </div>
    );
  }

  // ============ Main App ============
  function App() {
    const [activeTab, setActiveTab] = React.useState("monitor");

    return (
      <div style={{ minHeight: "100vh", background: "#f0f2f5" }}>
        <div style={{ background: "#001529", padding: "0 16px", marginBottom: 0 }}>
          <div style={{ color: "#fff", fontSize: 18, height: 48, lineHeight: "48px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span>系统监控</span>
            <Button type="link" style={{ color: "#fff" }} onClick={() => setActiveTab("config")}>设置</Button>
          </div>
        </div>

        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key)}
          style={{ padding: "0 16px" }}
          items={[
            { key: "monitor", label: "监控面板", children: <MonitorPage /> },
            { key: "config", label: "配置", children: <ConfigPage /> },
          ]}
        />
      </div>
    );
  }

  // ============ Register Routes ============
  if ((window as any).QwenPaw) {
    (window as any).QwenPaw.registerRoutes("system-monitor", [{
      path: "/plugin/system-monitor",
      component: App,
      label: "系统监控",
      icon: "📊",
      priority: 50,
    }]);
  }
})();
