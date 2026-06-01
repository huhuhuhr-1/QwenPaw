// GitHub Trending 插件前端入口 — 5 个 Tab 暗色主题。

import type * as ReactNS from "react";
import TrendingPage from "./pages/TrendingPage";
import ReposPage from "./pages/ReposPage";
import MonitorPage from "./pages/MonitorPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import { ROOT_CLASS, THEME_CSS } from "./styles";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;
const { Tabs } = host.antd;
const { TabPane } = Tabs;

function App() {
  const [activeTab, setActiveTab] = React.useState("trending");

  return (
    <div className={ROOT_CLASS} style={{ height: "100%" }}>
      <style dangerouslySetInnerHTML={{ __html: THEME_CSS }} />
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        style={{ height: "100%", padding: "0 16px" }}
      >
        <TabPane tab="🔥 热榜" key="trending">
          <TrendingPage />
        </TabPane>
        <TabPane tab="📦 仓库" key="repos">
          <ReposPage />
        </TabPane>
        <TabPane tab="📡 订阅" key="monitor">
          <MonitorPage />
        </TabPane>
        <TabPane tab="📊 报告" key="reports">
          <ReportsPage />
        </TabPane>
        <TabPane tab="⚙️ 设置" key="settings">
          <SettingsPage />
        </TabPane>
      </Tabs>
    </div>
  );
}

window.QwenPaw.registerRoutes?.("github-trending", [
  {
    path: "/plugin/github-trending",
    component: App,
    label: "热榜",
    icon: "📊",
    priority: 10,
  },
]);
