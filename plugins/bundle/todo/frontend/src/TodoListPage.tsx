import type * as ReactNS from "react";
import type { StatusFilter, TodoItem } from "./types";
import { listTodos, updateTodoStatus } from "./api";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;
const antd = host.antd;

const {
  Card,
  Table,
  Input,
  Select,
  DatePicker,
  Space,
  Button,
  Tag,
  Typography,
  message,
  Tooltip,
} = antd;

const { Title, Text: AntText } = Typography;
const { RangePicker } = DatePicker;

const STATUS_COLORS: Record<string, string> = {
  pending: "default",
  in_progress: "processing",
  completed: "success",
  cancelled: "error",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  cancelled: "Cancelled",
};

function formatTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleString("zh-CN", { hour2Digit: false });
}

function TodoListPage() {
  const [items, setItems] = React.useState<TodoItem[]>([]);
  const [loading, setLoading] = React.useState(false);

  const [keyword, setKeyword] = React.useState("");
  const [status, setStatus] = React.useState<StatusFilter>("all");
  const [dateRange, setDateRange] = React.useState<[number, number] | null>(null);

  const refresh = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await listTodos({
        status: status !== "all" ? status : undefined,
        keyword: keyword || undefined,
        time_from: dateRange ? dateRange[0] : undefined,
        time_to: dateRange ? dateRange[1] : undefined,
        limit: 100,
      });
      setItems(data.items || []);
    } catch (e: any) {
      message.error(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [keyword, status, dateRange]);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleStatusChange = async (taskId: string, newStatus: string) => {
    try {
      await updateTodoStatus(taskId, newStatus);
      message.success("Status updated");
      await refresh();
    } catch (e: any) {
      message.error(e?.message || String(e));
    }
  };

  const columns = [
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 120,
      render: (status: string, row: TodoItem) =>
        React.createElement(
          Select,
          {
            value: status,
            size: "small",
            style: { width: 110 },
            onChange: (val: string) => void handleStatusChange(row.id, val),
          },
          ["pending", "in_progress", "completed", "cancelled"].map((s) =>
            React.createElement(Select.Option, { key: s, value: s }, STATUS_LABELS[s]),
          ),
        ),
    },
    {
      title: "Description",
      dataIndex: "description",
      key: "description",
      ellipsis: true,
      render: (text: string) =>
        React.createElement(
          Tooltip,
          { title: text },
          React.createElement(AntText, null, text),
        ),
    },
    {
      title: "Agent",
      dataIndex: "agent_name",
      key: "agent_name",
      width: 120,
      render: (text: string) =>
        React.createElement(AntText, { type: "secondary", ellipsis: true }, text),
    },
    {
      title: "Session",
      dataIndex: "session_title",
      key: "session_title",
      width: 140,
      render: (text: string | null, row: TodoItem) =>
        React.createElement(
          AntText,
          { type: "secondary", ellipsis: true },
          text || `Session ${row.session_id.slice(0, 8)}…`,
        ),
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 160,
      render: (ts: number) =>
        React.createElement(AntText, { type: "secondary", style: { fontSize: 12 } },
          formatTime(ts),
        ),
    },
    {
      title: "Updated",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 160,
      render: (ts: number) =>
        React.createElement(AntText, { type: "secondary", style: { fontSize: 12 } },
          formatTime(ts),
        ),
    },
  ];

  return React.createElement(
    Card,
    { style: { maxWidth: 1100, margin: "24px auto" } },
    React.createElement(
      Space,
      { direction: "vertical", size: "large", style: { width: "100%" } },
      [
        // Header
        React.createElement(
          "div",
          { key: "h" },
          React.createElement(Title, { level: 3, style: { marginBottom: 4 } }, "Tasks"),
          React.createElement(
            AntText,
            { type: "secondary" },
            "Track tasks created by agents during conversations.",
          ),
        ),

        // Filter bar
        React.createElement(
          Space,
          { key: "filters", wrap: true },
          React.createElement(Input, {
            placeholder: "Search description…",
            value: keyword,
            onChange: (e: any) => setKeyword(e.target.value),
            style: { width: 200 },
            allowClear: true,
          }),
          React.createElement(
            Select,
            {
              value: status,
              onChange: (val: StatusFilter) => setStatus(val),
              style: { width: 140 },
            },
            React.createElement(Select.Option, { key: "all", value: "all" }, "All Status"),
            ["pending", "in_progress", "completed", "cancelled"].map((s) =>
              React.createElement(Select.Option, { key: s, value: s }, STATUS_LABELS[s]),
            ),
          ),
          React.createElement(RangePicker, {
            onChange: (vals: any) => {
              if (vals && vals[0] && vals[1]) {
                setDateRange([vals[0].unix(), vals[1].unix()]);
              } else {
                setDateRange(null);
              }
            },
            showTime: true,
          }),
          React.createElement(
            Button,
            { onClick: () => void refresh(), loading },
            "Refresh",
          ),
        ),

        // Table
        React.createElement(Table, {
          key: "tbl",
          rowKey: "id",
          loading,
          dataSource: items,
          columns,
          pagination: { pageSize: 50, showSizeChanger: true },
          locale: { emptyText: "No tasks yet." },
        }),
      ],
    ),
  );
}

export { TodoListPage };
