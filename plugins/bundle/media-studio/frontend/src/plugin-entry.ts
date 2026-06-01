/// <reference types="../../../console/src/global" />

(function () {
  const host = window.QwenPaw.host;
  const React = host.React;

  const antd = host.antd;
  const {
    UploadOutlined, ReloadOutlined, DeleteOutlined, DownloadOutlined,
    PauseOutlined, CaretRightOutlined, EyeOutlined, SaveOutlined,
    CheckCircleOutlined, CloseCircleOutlined, CloudOutlined, ThunderboltOutlined,
    HourglassOutlined, InboxOutlined, ArrowLeftOutlined, StopOutlined,
    RedoOutlined, SearchOutlined,
  } = window.antdIcons || {};

  const {
    Table, Tag, Button, Upload, message, Modal, Popconfirm, Space, Typography,
    Progress, Select, Card, Row, Col, Statistic, Switch, Form, Input,
    InputNumber, Alert, Divider, Tooltip, Spin, Timeline, Empty,
  } = antd;

  const { Title, Text: TypographyText, Paragraph } = Typography;
  const { Password } = Input;

  // ── API ──────────────────────────────────────────────────────────
  const API_BASE = "http://localhost:7899";

  async function api(method: string, url: string, body?: unknown) {
    const opts: RequestInit = {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    };
    const res = await fetch(`${API_BASE}${url}`, opts);
    if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => res.statusText)}`);
    if ((res.headers.get("content-type") || "").includes("application/json")) return res.json();
    return res;
  }

  async function uploadFile(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.json();
  }

  async function createWorkflow(fileId: string) {
    return api("POST", "/workflows", { file_id: fileId });
  }

  async function listWorkflows(page = 1, pageSize = 20) {
    return api("GET", `/workflows?${new URLSearchParams({ page: String(page), page_size: String(pageSize) })}`);
  }

  async function deleteWorkflow(id: string, force = false) {
    return api("DELETE", `/workflows/${id}${force ? "?force=true" : ""}`);
  }

  async function batchDeleteWorkflows(ids: string[], force = false) {
    return api("POST", `/workflows/batch-delete${force ? "?force=true" : ""}`, { workflow_ids: ids });
  }

  async function batchExportWorkflows(ids: string[]) {
    const res = await fetch(`${API_BASE}/workflows/batch-export`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workflow_ids: ids }),
    });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
    return res.blob();
  }

  function downloadBlob(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    URL.revokeObjectURL(url);
  }

  async function getWorkflowQueueStats() { return api("GET", "/workflows/queue-stats"); }
  async function pauseQueueLane(lane: string) { await api("POST", `/queues/${lane}/pause`); }
  async function resumeQueueLane(lane: string) { await api("POST", `/queues/${lane}/resume`); }
  async function pauseAllQueues() { await api("POST", "/queues/pause-all"); }
  async function resumeAllQueues() { await api("POST", "/queues/resume-all"); }

  async function listGlobalLogs(page = 1, pageSize = 50, level?: string, workflowId?: string) {
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (level) q.set("level", level);
    if (workflowId) q.set("workflow_id", workflowId);
    return api("GET", `/logs?${q}`);
  }

  async function listArtifacts(page = 1, pageSize = 20, stepType?: string) {
    const q = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (stepType) q.set("step_type", stepType);
    return api("GET", `/artifacts?${q}`);
  }

  async function batchDownloadArtifacts(fileIds: string[]) {
    const res = await fetch(`${API_BASE}/artifacts/batch-download`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file_ids: fileIds }),
    });
    if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => res.statusText)}`);
    return res.blob();
  }

  async function getProcessorConfig() { return api("GET", "/config"); }
  async function updateProcessorConfig(body: Record<string, unknown>) { return api("PUT", "/config", body); }

  async function getWorkflow(id: string) { return api("GET", `/workflows/${id}`); }
  async function getWorkflowLogs(id: string) { return api("GET", `/workflows/${id}/logs`); }
  async function getWorkflowResults(id: string) { return api("GET", `/workflows/${id}/results`); }
  async function retryStep(id: string) { return api("POST", `/steps/${id}/retry`); }
  async function cancelStep(id: string) { return api("POST", `/steps/${id}/cancel`); }
  async function pauseWorkflow(id: string) { await api("POST", `/workflows/${id}/pause`); }
  async function resumeWorkflow(id: string) { await api("POST", `/workflows/${id}/resume`); }
  async function batchPauseWorkflows(ids: string[]) { return api("POST", "/workflows/batch-pause", { workflow_ids: ids }); }
  async function batchResumeWorkflows(ids: string[]) { return api("POST", "/workflows/batch-resume", { workflow_ids: ids }); }

  async function fetchArtifactText(url: string) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status}: ${await res.text().catch(() => res.statusText)}`);
    return res.text();
  }

  // ── Helpers ──────────────────────────────────────────────────────
  const ARTIFACT_PATH_BY_STEP: Record<string, string> = {
    extract_audio: "/audio", transcribe: "/document", polish: "/polished",
    audio: "/audio", markdown: "/document",
  };

  function getFilePreviewUrl(fileId: string, opts?: { stepType?: string; downloadUrl?: string }) {
    let path: string;
    if (opts?.downloadUrl) path = opts.downloadUrl.split("?")[0];
    else if (opts?.stepType && ARTIFACT_PATH_BY_STEP[opts.stepType])
      path = `${ARTIFACT_PATH_BY_STEP[opts.stepType]}/${fileId}`;
    else path = `/files/${fileId}`;
    return `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  }

  function getFileDownloadUrl(fileId: string, opts?: { stepType?: string; downloadUrl?: string }) {
    if (opts?.downloadUrl) return `${API_BASE}${opts.downloadUrl.split("?")[0]}?download=true`;
    if (opts?.stepType && ARTIFACT_PATH_BY_STEP[opts.stepType])
      return `${API_BASE}${ARTIFACT_PATH_BY_STEP[opts.stepType]}/${fileId}`;
    return `${API_BASE}/files/${fileId}?download=true`;
  }

  const TEXT_STEP_TYPES = new Set(["transcribe", "polish"]);
  const AUDIO_EXT = new Set([".mp3", ".m4a", ".wav", ".flac", ".ogg", ".aac", ".wma"]);
  const VIDEO_EXT = new Set([".mp4", ".webm", ".mkv", ".avi", ".mov", ".flv"]);

  function getArtifactKind(stepType: string, fileName: string): "audio" | "video" | "text" {
    const ext = fileName.includes(".") ? fileName.slice(fileName.lastIndexOf(".")).toLowerCase() : "";
    if (stepType === "extract_audio" || AUDIO_EXT.has(ext)) return "audio";
    if (stepType === "video" || VIDEO_EXT.has(ext)) return "video";
    if (TEXT_STEP_TYPES.has(stepType) || ext === ".txt" || ext === ".md" || ext === ".markdown") return "text";
    if (VIDEO_EXT.has(ext)) return "video";
    return "text";
  }

  function formatDateTime(t: string) {
    if (!t) return "";
    try {
      const normalized = t.includes("T") ? t : t.replace(" ", "T");
      const iso = /[zZ]|[+-]\d{2}:\d{2}$/.test(normalized) ? normalized : `${normalized}Z`;
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return t;
      return d.toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
    } catch { return t; }
  }

  function formatSize(s: number) {
    if (s < 1024) return `${s} B`;
    if (s < 1024 * 1024) return `${(s / 1024).toFixed(1)} KB`;
    return `${(s / 1024 / 1024).toFixed(1)} MB`;
  }

  function formatDuration(seconds: number | null | undefined) {
    if (seconds == null || seconds < 0) return "—";
    if (seconds < 1) return "<1 秒";
    if (seconds < 60) return `${Math.round(seconds)} 秒`;
    const m = Math.floor(seconds / 60);
    const s = Math.round(seconds % 60);
    if (m < 60) return s > 0 ? `${m} 分 ${s} 秒` : `${m} 分`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    return rm > 0 ? `${h} 时 ${rm} 分` : `${h} 时`;
  }

  const STATUS_COLORS: Record<string, string> = {
    pending: "default", processing: "processing", paused: "warning",
    completed: "success", failed: "error",
  };
  const STATUS_LABELS: Record<string, string> = {
    pending: "等待中", processing: "处理中", paused: "已暂停",
    completed: "已完成", failed: "失败",
  };
  const STEP_LABELS: Record<string, string> = {
    extract_audio: "抽取音频", transcribe: "语音转写", polish: "文本精修",
  };
  const ACCEPT = ".mp4,.webm,.mkv,.avi,.mov,.mp3,.wav,.flac,.ogg,.aac,.m4a,.md,.txt,.markdown";

  // ── ArtifactPreviewModal ─────────────────────────────────────────
  function ArtifactPreviewModal({ target, onClose }: {
    target: { fileId: string; stepType: string; fileName: string; downloadUrl?: string } | null;
    onClose: () => void;
  }) {
    const [loading, setLoading] = React.useState(false);
    const [text, setText] = React.useState("");
    const [error, setError] = React.useState("");
    const kind = target ? getArtifactKind(target.stepType, target.fileName) : null;

    React.useEffect(() => {
      if (!target || kind !== "text") { setText(""); setError(""); return; }
      let cancelled = false;
      setLoading(true); setError("");
      fetchArtifactText(getFilePreviewUrl(target.fileId, { stepType: target.stepType, downloadUrl: target.downloadUrl }))
        .then((body) => { if (!cancelled) setText(body); })
        .catch((e: unknown) => { if (!cancelled) setError(e instanceof Error ? e.message : String(e)); })
        .finally(() => { if (!cancelled) setLoading(false); });
      return () => { cancelled = true; };
    }, [target?.fileId, target?.fileName, kind]);

    const title = target ? `预览 · ${target.fileName}` : "预览";
    const urlOpts = target ? { stepType: target.stepType, downloadUrl: target.downloadUrl } : undefined;

    return React.createElement(Modal, {
      open: !!target, title, onCancel: onClose,
      footer: target ? React.createElement(Button, {
        icon: React.createElement(DownloadOutlined),
        href: getFileDownloadUrl(target.fileId, urlOpts), target: "_blank",
      }, "下载") : null,
      width: kind === "text" ? 720 : 640, destroyOnHidden: true,
    }, !target ? null : kind === "audio"
      ? React.createElement("audio", { controls: true, autoPlay: true, style: { width: "100%" }, src: getFilePreviewUrl(target.fileId, urlOpts) }, "您的浏览器不支持音频播放")
      : kind === "video"
        ? React.createElement("video", { controls: true, autoPlay: true, style: { width: "100%", maxHeight: "70vh" }, src: getFilePreviewUrl(target.fileId, urlOpts) }, "您的浏览器不支持视频播放")
        : loading
          ? React.createElement(Spin, null)
          : error
            ? React.createElement(TypographyText, { type: "danger" }, error)
            : React.createElement("pre", { style: { maxHeight: "60vh", overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word", margin: 0, padding: 12, background: "#fafafa", borderRadius: 6, fontSize: 13, lineHeight: 1.6 } }, text || "(空文件)"));
  }

  // ── FileListPage ──────────────────────────────────────────────────
  function FileListPage({ onViewDetail }: { onViewDetail: (id: string) => void }) {
    const [data, setData] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState(0);
    const [page, setPage] = React.useState(1);
    const [pageSize, setPageSize] = React.useState(20);
    const [loading, setLoading] = React.useState(false);
    const [uploading, setUploading] = React.useState(false);
    const [exporting, setExporting] = React.useState(false);
    const [deleting, setDeleting] = React.useState(false);
    const [selectedKeys, setSelectedKeys] = React.useState<string[]>([]);
    const [uploadProg, setUploadProg] = React.useState({ cur: 0, total: 0, name: "" });
    const [searchText, setSearchText] = React.useState("");
    const batchRunning = React.useRef(false);

    const load = React.useCallback(async () => {
      setLoading(true);
      try {
        const res = await listWorkflows(page, pageSize);
        setData(res.items);
        setTotal(res.total);
      } catch (e: unknown) {
        message.error("加载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setLoading(false); }
    }, [page, pageSize]);

    React.useEffect(() => { load(); }, [load]);

    // auto page-back when current page becomes empty
    React.useEffect(() => {
      if (!loading && data.length === 0 && total > 0 && page > 1) {
        setPage((p) => p - 1);
      }
    }, [loading, data.length, total, page]);

    const processBatch = React.useCallback(async (files: File[]) => {
      if (!files.length || batchRunning.current) return;
      batchRunning.current = true;
      setUploading(true);
      let ok = 0; const errors: string[] = [];
      for (let i = 0; i < files.length; i++) {
        const f = files[i];
        try {
          setUploadProg({ cur: i, total: files.length, name: f.name });
          await createWorkflow((await uploadFile(f)).file_id);
          ok++;
        } catch (e: unknown) {
          errors.push(`${f.name}: ${e instanceof Error ? e.message : String(e)}`);
        }
        setUploadProg({ cur: i + 1, total: files.length, name: f.name });
      }
      batchRunning.current = false;
      setUploading(false);
      setUploadProg({ cur: 0, total: 0, name: "" });
      if (ok > 0) { message.success(`已创建 ${ok} 个处理任务`); setPage(1); await load(); }
      if (errors.length > 0) {
        message.error(
          errors.length === files.length ? `上传失败：${errors[0]}` : `${errors.length} 个失败：${errors[0]}`,
          8,
        );
      }
    }, [load]);

    const handleBeforeUpload = (file: File, fileList: File[]) => {
      if (file === fileList[fileList.length - 1]) processBatch(fileList);
      return false;
    };

    const handleBatchDelete = async (force = false) => {
      if (!selectedKeys.length) return;
      setDeleting(true);
      try {
        const res = await batchDeleteWorkflows(selectedKeys, force);
        if (res.deleted_count > 0) message.success(`已删除 ${res.deleted_count} 个任务`);
        if (res.error_count > 0) {
          const processing = res.errors?.some((e: any) => e.code === 409);
          if (processing && !force) {
            Modal.confirm({
              title: "部分任务正在处理中",
              content: "是否强制删除？将移除任务记录及已生成的文件。",
              okText: "强制删除",
              okButtonProps: { danger: true },
              onOk: () => handleBatchDelete(true),
            });
            return;
          }
          message.warning(`${res.error_count} 个任务删除失败`);
        }
        setSelectedKeys([]);
        await load();
      } catch (e: unknown) {
        message.error("删除失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setDeleting(false); }
    };

    const handleBatchExport = async () => {
      if (!selectedKeys.length) return;
      setExporting(true);
      try {
        downloadBlob(await batchExportWorkflows(selectedKeys), `tasks-export-${selectedKeys.length}.zip`);
        message.success("导出已开始下载");
      } catch (e: unknown) {
        message.error("导出失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setExporting(false); }
    };

    const handleBatchPause = async () => {
      if (!selectedKeys.length) return;
      try {
        const res = await batchPauseWorkflows(selectedKeys);
        message.success(`已停止 ${res.updated.length} 个任务`);
        await load();
      } catch (e: unknown) {
        message.error("批量停止失败: " + (e instanceof Error ? e.message : String(e)));
      }
    };

    const handleBatchResume = async () => {
      if (!selectedKeys.length) return;
      try {
        const res = await batchResumeWorkflows(selectedKeys);
        message.success(`已启动 ${res.updated.length} 个任务`);
        await load();
      } catch (e: unknown) {
        message.error("批量启动失败: " + (e instanceof Error ? e.message : String(e)));
      }
    };

    const handlePauseOne = async (id: string) => {
      try { await pauseWorkflow(id); message.success("已停止任务（暂停）"); await load(); }
      catch (e: unknown) { message.error("停止失败: " + (e instanceof Error ? e.message : String(e))); }
    };

    const handleResumeOne = async (id: string) => {
      try { await resumeWorkflow(id); message.success("已启动任务"); await load(); }
      catch (e: unknown) { message.error("启动失败: " + (e instanceof Error ? e.message : String(e))); }
    };

    const handleDeleteOne = async (id: string, force = false) => {
      try {
        await deleteWorkflow(id, force);
        message.success("已删除");
        setSelectedKeys((k) => k.filter((x) => x !== id));
        await load();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        if (msg.includes("409") || msg.includes("processing")) {
          Modal.confirm({
            title: "任务正在处理",
            content: "强制删除该任务？",
            okText: "强制删除", okButtonProps: { danger: true },
            onOk: () => handleDeleteOne(id, true),
          });
          return;
        }
        message.error("删除失败: " + msg);
      }
    };

    // local search filter
    const filtered = searchText
      ? data.filter((r: any) =>
          (r.entry_file_name || "").toLowerCase().includes(searchText.toLowerCase())
          || (r.workflow_id || "").toLowerCase().includes(searchText.toLowerCase()))
      : data;

    const busy = uploading || deleting || exporting;

    const columns: any[] = [
      { title: "序号", key: "index", width: 72, align: "center",
        render: (_v: any, _r: any, idx: number) => (page - 1) * pageSize + idx + 1 },
      { title: "文件", dataIndex: "entry_file_name", key: "name",
        render: (name: string, r: any) =>
          React.createElement(Button, { type: "link", style: { padding: 0 },
            onClick: () => onViewDetail(r.workflow_id) }, name) },
      { title: "类型", dataIndex: "entry_type", key: "type", width: 90 },
      { title: "状态", dataIndex: "status", key: "status", width: 110,
        render: (s: string) => React.createElement(Tag, { color: STATUS_COLORS[s] }, STATUS_LABELS[s] || s) },
      { title: "进度", key: "progress", width: 80,
        render: (_: any, r: any) => `${r.completed_count}/${r.step_count}` },
      { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 180,
        render: (t: string) => formatDateTime(t) },
      { title: "操作", key: "actions", width: 280,
        render: (_: any, r: any) =>
          React.createElement(Space, { size: "small", wrap: true },
            (r.status === "paused" || r.status === "pending")
              ? React.createElement(Button, { size: "small", type: "link", icon: React.createElement(CaretRightOutlined),
                  onClick: () => handleResumeOne(r.workflow_id) }, "启动")
              : null,
            (r.status === "processing" || r.status === "pending")
              ? React.createElement(Button, { size: "small", type: "link", danger: true, icon: React.createElement(PauseOutlined),
                  onClick: () => handlePauseOne(r.workflow_id) }, "停止")
              : null,
            React.createElement(Button, { size: "small", type: "link",
              onClick: () => onViewDetail(r.workflow_id) }, "详情"),
            React.createElement(Popconfirm, { title: "删除此任务及关联文件？",
              onConfirm: () => handleDeleteOne(r.workflow_id),
              okText: "删除", cancelText: "取消", okButtonProps: { danger: true } },
              React.createElement(Button, { size: "small", type: "link", danger: true }, "删除")),
          ) },
    ];

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "任务管理"),
        React.createElement(Space, { wrap: true },
          selectedKeys.length > 0 && React.createElement(React.Fragment, null,
            React.createElement(TypographyText, { type: "secondary" }, `已选 ${selectedKeys.length} 项`),
            React.createElement(Button, { icon: React.createElement(CaretRightOutlined), disabled: busy,
              onClick: handleBatchResume }, "批量启动"),
            React.createElement(Button, { icon: React.createElement(PauseOutlined), disabled: busy,
              onClick: handleBatchPause }, "批量停止"),
            React.createElement(Button, { icon: React.createElement(DownloadOutlined), loading: exporting,
              disabled: busy, onClick: handleBatchExport }, "批量导出"),
            React.createElement(Popconfirm, {
              title: `删除选中的 ${selectedKeys.length} 个任务？`,
              description: "将删除任务记录及未被其他任务引用的文件",
              onConfirm: () => handleBatchDelete(),
              okText: "删除", cancelText: "取消", okButtonProps: { danger: true } },
              React.createElement(Button, { danger: true, icon: React.createElement(DeleteOutlined),
                loading: deleting, disabled: busy }, "批量删除")),
          ),
          React.createElement(Input.Search, {
            placeholder: "搜索文件名/ID", value: searchText,
            onChange: (e: any) => setSearchText(e.target.value),
            onSearch: (v: string) => setSearchText(v),
            style: { width: 200 },
            allowClear: true,
          }),
          React.createElement(Upload, { multiple: true, beforeUpload: handleBeforeUpload,
            showUploadList: false, accept: ACCEPT, disabled: busy },
            React.createElement(Button, { type: "primary", icon: React.createElement(UploadOutlined),
              loading: uploading }, "批量上传")),
          React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: load,
            disabled: busy }, "刷新"),
        )),
      React.createElement(Upload.Dragger, { multiple: true, showUploadList: false, accept: ACCEPT,
        disabled: busy, beforeUpload: handleBeforeUpload, style: { marginBottom: 16 } },
        React.createElement("p", { className: "ant-upload-drag-icon" }, React.createElement(InboxOutlined)),
        React.createElement("p", { className: "ant-upload-text" }, "点击或拖拽多个文件到此处上传"),
        React.createElement("p", { className: "ant-upload-hint" }, "支持视频、音频、Markdown/文本"),
      ),
      uploading && React.createElement(Modal, { open: true, title: "正在批量上传", footer: null, closable: false, maskClosable: false },
        React.createElement(Progress, { percent: uploadProg.total ? Math.round(uploadProg.cur / uploadProg.total * 100) : 0, status: "active" }),
        React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginTop: 8 } },
          `${uploadProg.cur}/${uploadProg.total}${uploadProg.name ? ` · ${uploadProg.name}` : ""}`)),
      React.createElement(Table, {
        rowKey: "workflow_id",
        columns,
        dataSource: filtered,
        loading,
        rowSelection: { selectedRowKeys: selectedKeys, onChange: (keys: any) => setSelectedKeys(keys) },
        pagination: {
          current: page, pageSize, total, showSizeChanger: true,
          pageSizeOptions: [10, 20, 50, 100],
          showTotal: (t: number) => `共 ${t} 条`,
          onChange: (p: number, ps: number) => { setPage(p); setPageSize(ps); },
        },
      }));
  }

  // ── WorkflowStatusPage ───────────────────────────────────────────
  const WF_STEP_LABELS: Record<string, string> = {
    extract_audio: "抽取音频", transcribe: "语音转写", polish: "文本精修",
  };

  function WorkflowStatusPage({ workflowId, onBack, onViewResults }: {
    workflowId: string; onBack: () => void; onViewResults: (id: string) => void;
  }) {
    const [wf, setWf] = React.useState<any>(null);
    const [logs, setLogs] = React.useState<any[]>([]);
    const [artifacts, setArtifacts] = React.useState<any[]>([]);
    const [preview, setPreview] = React.useState<any>(null);
    const [initialLoading, setInitialLoading] = React.useState(true);
    const logEndRef = React.useRef<HTMLDivElement>(null);

    const load = React.useCallback(async (silent = false) => {
      if (!silent) setInitialLoading(true);
      try {
        const [detail, logEntries, results] = await Promise.all([
          getWorkflow(workflowId),
          getWorkflowLogs(workflowId),
          getWorkflowResults(workflowId).catch(() => ({ workflow_id: workflowId, files: [] })),
        ]);
        setWf(detail);
        setLogs(logEntries);
        setArtifacts(results.files);
      } catch (e: unknown) {
        message.error("加载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setInitialLoading(false); }
    }, [workflowId]);

    React.useEffect(() => {
      load(false);
      const timer = window.setInterval(() => load(true), 2000);
      return () => window.clearInterval(timer);
    }, [load]);

    React.useEffect(() => {
      logEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [logs]);

    const handleRetry = async (stepId: string) => {
      try { await retryStep(stepId); message.success("已重新执行该步骤"); load(true); }
      catch (e: unknown) { message.error("重试失败: " + (e instanceof Error ? e.message : String(e))); }
    };

    const handleCancel = async (stepId: string) => {
      Modal.confirm({
        title: "取消该步骤？",
        content: "后续未开始的步骤也会被取消。",
        onOk: async () => {
          try { await cancelStep(stepId); message.success("已取消"); load(true); }
          catch (e: unknown) { message.error("取消失败: " + (e instanceof Error ? e.message : String(e))); }
        },
      });
    };

    if (initialLoading && !wf) return React.createElement(Spin, { style: { display: "block", marginTop: 100 } });

    const steps: any[] = wf?.steps || [];
    const done = steps.filter((s: any) => s.status === "completed").length;
    const total = steps.length;
    const pct = total ? Math.round((done / total) * 100) : 0;
    const active = steps.find((s: any) => s.status === "processing");

    const statusColors: Record<string, string> = {
      pending: "default", processing: "processing", completed: "success",
      failed: "error", cancelled: "default",
    };

    function stepHint(s: any, steps: any[]) {
      if (s.status === "pending" && s.depends_on) {
        const dep = steps.find((x: any) => x.id === s.depends_on);
        if (dep?.status !== "completed") {
          return `等待上一步「${WF_STEP_LABELS[dep?.step_type] || dep?.step_type}」完成`;
        }
      }
      if (s.status === "pending") return "排队中，即将开始";
      if (s.status === "processing") return "正在执行…";
      return null;
    }

    const logLevelColor: Record<string, string> = {
      INFO: "#52c41a", WARN: "#faad14", ERROR: "#ff4d4f",
    };

    function StepDot({ status }: { status: string }) {
      const colors: Record<string, string> = {
        pending: "#d9d9d9", processing: "#1677ff", completed: "#52c41a",
        failed: "#ff4d4f", cancelled: "#bfbfbf",
      };
      return React.createElement("span", {
        style: {
          color: colors[status] || "gray", fontSize: 16,
          animation: status === "processing" ? "wf-pulse 1.2s infinite" : undefined,
        },
      }, "●");
    }

    function formatTime(iso?: string | null) { return iso ? formatDateTime(iso) : "—"; }

    const artifactsByStep: Record<string, any> = {};
    for (const a of artifacts) { artifactsByStep[a.file_id] = a; }

    return React.createElement("div", null,
      React.createElement("style", null, `@keyframes wf-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }`),
      React.createElement("div", { style: { display: "flex", gap: 12, alignItems: "center", marginBottom: 16, flexWrap: "wrap" } },
        React.createElement(Button, { icon: React.createElement(ArrowLeftOutlined), onClick: onBack }, "返回列表"),
        React.createElement(Title, { level: 4, style: { margin: 0 } }, wf?.entry_file_name || workflowId),
        React.createElement(Tag, null, wf?.entry_type),
        React.createElement(Tag, { color: statusColors[wf?.status || ""] }, wf?.status),
        React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: () => load(true) }, "刷新"),
        wf?.status === "completed" && React.createElement(Button, { type: "primary",
          onClick: () => onViewResults(workflowId) }, "查看产出"),
      ),
      React.createElement(Card, { size: "small", style: { marginBottom: 16 } },
        React.createElement("div", { style: { marginBottom: 8 } },
          `总进度 ${done}/${total} 步`,
          active && React.createElement("span", { style: { marginLeft: 12, color: "#1677ff" } },
            `当前：${WF_STEP_LABELS[active.step_type] || active.step_type}`),
        ),
        React.createElement(Progress, {
          percent: pct,
          status: wf?.status === "failed" ? "exception" : wf?.status === "completed" ? "success" : "active",
        }),
      ),
      wf?.status === "processing" && React.createElement(Alert, {
        type: "info", showIcon: true, style: { marginBottom: 16 },
        message: "任务执行中",
        description: "转写长音频可能需数分钟，下方「执行日志」会每 2 秒自动刷新。",
      }),
      React.createElement(Card, { title: "处理步骤", style: { marginBottom: 16 } },
        steps.length === 0
          ? React.createElement(Empty, { description: "暂无步骤" })
          : React.createElement(Timeline, null, steps.map((s: any) => {
              const hint = stepHint(s, steps);
              const art = s.output_file_id ? artifactsByStep[s.output_file_id] : null;
              return React.createElement(Timeline.Item, { key: s.id, dot: React.createElement(StepDot, { status: s.status }) },
                React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 } },
                  React.createElement("div", { style: { flex: 1 } },
                    React.createElement("strong", null, WF_STEP_LABELS[s.step_type] || s.step_type),
                    React.createElement(Tag, { color: statusColors[s.status], style: { marginLeft: 8 } }, s.status),
                    hint && React.createElement("div", { style: { color: "#1677ff", fontSize: 12, marginTop: 4 } }, hint),
                    React.createElement("div", { style: { color: "#888", fontSize: 12, marginTop: 4 } },
                      `开始: ${formatTime(s.started_at)} · 结束: ${formatTime(s.completed_at)}`),
                    s.output_file_id && s.status === "completed" && React.createElement("div", { style: { marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" } },
                      React.createElement(Button, { size: "small", icon: React.createElement(EyeOutlined),
                        onClick: () => setPreview({ fileId: s.output_file_id, stepType: s.step_type, fileName: art?.name || s.output_file_id }) }, "预览"),
                      React.createElement(Button, { size: "small", icon: React.createElement(DownloadOutlined),
                        href: getFileDownloadUrl(s.output_file_id, { stepType: s.step_type, downloadUrl: art?.download_url }),
                        target: "_blank" }, "下载"),
                    ),
                    s.error && React.createElement("div", { style: { color: "#ff4d4f", fontSize: 12, marginTop: 4, whiteSpace: "pre-wrap" } }, s.error),
                  ),
                  React.createElement("div", null,
                    s.status === "failed" && React.createElement(Button, { size: "small", icon: React.createElement(RedoOutlined),
                      onClick: () => handleRetry(s.id) }, "重试"),
                    s.status === "processing" && React.createElement(Button, { size: "small", icon: React.createElement(StopOutlined),
                      onClick: () => handleCancel(s.id), danger: true }, "取消"),
                  ),
                ),
              );
            })),
      ),
      React.createElement(Card, { title: `中间产物 (${artifacts.length})`, style: { marginBottom: 16 } },
        wf && (wf.entry_type === "video" || wf.entry_type === "audio") && React.createElement("div", { style: { marginBottom: 12, display: "flex", alignItems: "center", gap: 8 } },
          React.createElement(TypographyText, null, `原始文件：${wf.entry_file_name}`),
          React.createElement(Button, { size: "small", icon: React.createElement(EyeOutlined),
            onClick: () => setPreview({ fileId: wf.entry_file_id, stepType: wf.entry_type, fileName: wf.entry_file_name }) }, "预览"),
        ),
        artifacts.length === 0
          ? React.createElement(TypographyText, { type: "secondary" }, "步骤完成后，音频 / 文稿 / 精修稿会出现在这里，可即时预览。")
          : React.createElement("div", { style: { display: "flex", flexDirection: "column", gap: 8 } },
              artifacts.map((a: any) =>
                React.createElement("div", { key: a.file_id, style: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 12px", background: "#fafafa", borderRadius: 6 } },
                  React.createElement("div", null,
                    React.createElement(Tag, null, WF_STEP_LABELS[a.step_type] || a.step_type),
                    React.createElement("span", { style: { marginLeft: 8 } }, a.name),
                    React.createElement(TypographyText, { type: "secondary", style: { marginLeft: 8, fontSize: 12 } }, formatSize(a.size_bytes)),
                  ),
                  React.createElement(Space, null,
                    React.createElement(Button, { size: "small", icon: React.createElement(EyeOutlined),
                      onClick: () => setPreview({ fileId: a.file_id, stepType: a.step_type, fileName: a.name, downloadUrl: a.download_url }) }, "预览"),
                    React.createElement(Button, { size: "small", icon: React.createElement(DownloadOutlined),
                      href: getFileDownloadUrl(a.file_id, { stepType: a.step_type, downloadUrl: a.download_url }),
                      target: "_blank" }, "下载"),
                  ),
                ),
              ),
            ),
      ),
      React.createElement(Card, {
        title: `执行日志 (${logs.length})`,
        extra: React.createElement(TypographyText, { type: "secondary", style: { fontSize: 12 } }, "每 2 秒自动刷新"),
      },
        logs.length === 0
          ? React.createElement(TypographyText, { type: "secondary" }, "暂无日志。任务开始后会显示 ffmpeg / 转写 / 精修等记录。")
          : React.createElement("div", { style: { maxHeight: 360, overflow: "auto", fontFamily: "ui-monospace, monospace", fontSize: 12, background: "#1e1e1e", color: "#d4d4d4", padding: 12, borderRadius: 6, textAlign: "left", wordBreak: "break-word" } },
              logs.map((log: any) =>
                React.createElement("div", { key: log.id, style: { marginBottom: 6, lineHeight: 1.5, textAlign: "left" } },
                  React.createElement("span", { style: { color: "#888" } }, `[${formatDateTime(log.created_at)}]`),
                  " ",
                  React.createElement("span", { style: { color: logLevelColor[log.level] || "#aaa" } }, log.level),
                  " ",
                  React.createElement("span", { style: { color: "#69b1ff" } },
                    `[${WF_STEP_LABELS[log.step_type || ""] || log.step_type}]`),
                  " ",
                  log.message,
                ),
              ),
              React.createElement("div", { ref: logEndRef }),
            ),
      ),
      React.createElement(ArtifactPreviewModal, { target: preview, onClose: () => setPreview(null) }));
  }

  // ── FileResultsPage ──────────────────────────────────────────────
  function FileResultsPage({ workflowId, onBack }: { workflowId: string; onBack: () => void }) {
    const [results, setResults] = React.useState<any>(null);
    const [loading, setLoading] = React.useState(true);
    const [preview, setPreview] = React.useState<any>(null);

    const load = React.useCallback(async () => {
      setLoading(true);
      try {
        setResults(await getWorkflowResults(workflowId));
      } catch (e: unknown) {
        message.error("加载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setLoading(false); }
    }, [workflowId]);

    React.useEffect(() => { load(); }, [load]);

    if (loading && !results) return React.createElement(Spin, { style: { display: "block", marginTop: 100 } });

    const files: any[] = results?.files || [];

    const columns: any[] = [
      { title: "类型", dataIndex: "step_type", key: "type", width: 100,
        render: (t: string) => WF_STEP_LABELS[t] || t },
      { title: "文件", dataIndex: "name", key: "name" },
      { title: "大小", dataIndex: "size_bytes", key: "size", width: 100,
        render: (s: number) => formatSize(s) },
      { title: "操作", key: "actions", width: 180,
        render: (_: any, r: any) =>
          React.createElement(Space, { size: "small" },
            React.createElement(Button, { type: "link", size: "small", icon: React.createElement(EyeOutlined),
              onClick: () => setPreview({ fileId: r.file_id, stepType: r.step_type, fileName: r.name, downloadUrl: r.download_url }) }, "预览"),
            React.createElement(Button, { type: "link", size: "small", icon: React.createElement(DownloadOutlined),
              href: getFileDownloadUrl(r.file_id, { stepType: r.step_type, downloadUrl: r.download_url }),
              target: "_blank" }, "下载"),
          ),
      },
    ];

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", gap: 12, alignItems: "center", marginBottom: 16 } },
        React.createElement(Button, { icon: React.createElement(ArrowLeftOutlined), onClick: onBack }, "返回"),
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "产出文件"),
        React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: load }, "刷新"),
      ),
      React.createElement(Card, null,
        React.createElement(Table, { rowKey: "file_id", columns, dataSource: files, pagination: false }),
      ),
      React.createElement(ArtifactPreviewModal, { target: preview, onClose: () => setPreview(null) }));
  }

  // ── QueuePage ─────────────────────────────────────────────────────
  const LANE_ORDER = ["extract", "transcribe_fast", "transcribe_slow", "transcribe_external", "polish"];
  const LANE_COLORS: Record<string, string> = {
    extract: "#1677ff", transcribe_fast: "#9254de", transcribe_slow: "#722ed1",
    transcribe_external: "#eb2f96", polish: "#13c2c2",
  };

  function LaneCard({ laneKey, label, stats, paused, onPause, onResume }: {
    laneKey: string; label: string; stats: any; paused: boolean;
    onPause: () => void; onResume: () => void;
  }) {
    const color = LANE_COLORS[laneKey] ?? "#1677ff";
    const enabled = stats.enabled !== false;
    const showPaused = enabled && paused;

    return React.createElement(Card, {
      size: "small",
      style: { opacity: enabled ? 1 : 0.55 },
      title: React.createElement(Space, null,
        React.createElement("span", { style: { color } }, label),
        !enabled && React.createElement(Tag, null, "已关闭"),
        enabled && stats.available === false && React.createElement(Tag, { color: "warning" }, "未配置"),
        showPaused && React.createElement(Tag, { color: "orange" }, "已暂停"),
      ),
      extra: enabled
        ? showPaused
          ? React.createElement(Button, { size: "small", type: "link", icon: React.createElement(CaretRightOutlined),
              onClick: onResume }, "恢复")
          : React.createElement(Button, { size: "small", type: "link", danger: true, icon: React.createElement(PauseOutlined),
              onClick: onPause }, "暂停")
        : null,
      styles: { body: { paddingTop: 8 } },
    },
      React.createElement(Row, { gutter: [8, 12] },
        React.createElement(Col, { span: 8 },
          React.createElement(Statistic, { title: "运行中", value: stats.running, suffix: `/ ${stats.capacity}`,
            valueStyle: { color: stats.running > 0 ? "#1677ff" : undefined, fontSize: 20 } })),
        React.createElement(Col, { span: 8 },
          React.createElement(Statistic, { title: "排队", value: stats.queued,
            valueStyle: { color: stats.queued > 0 ? "#fa8c16" : undefined, fontSize: 20 } })),
        React.createElement(Col, { span: 8 },
          React.createElement(Statistic, { title: "已完成", value: stats.completed,
            valueStyle: { color: "#52c41a", fontSize: 20 } })),
      ),
    );
  }

  function QueuePage() {
    const [stats, setStats] = React.useState<any>(null);
    const [error, setError] = React.useState<string | null>(null);
    const [refreshToken, setRefreshToken] = React.useState(0);

    const load = React.useCallback(async () => {
      try { setStats(await getWorkflowQueueStats()); setError(null); }
      catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    }, []);

    React.useEffect(() => {
      load();
      const id = window.setInterval(() => load(), 2000);
      return () => window.clearInterval(id);
    }, [load, refreshToken]);

    const toggleLane = async (lane: string, pause: boolean) => {
      try { if (pause) await pauseQueueLane(lane); else await resumeQueueLane(lane); await load(); }
      catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    };

    const toggleAll = async (pause: boolean) => {
      try { if (pause) await pauseAllQueues(); else await resumeAllQueues(); await load(); }
      catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    };

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "队列管理"),
        React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: () => setRefreshToken((t) => t + 1) }, "刷新"),
      ),
      React.createElement(Paragraph, { type: "secondary", style: { marginBottom: 16 } },
        "监控抽音频、转写、精修三条全局队列的运行与排队情况；可暂停或恢复单条队列或全部队列（仅控制调度，不删除任务）。"),
      error && !stats ? React.createElement(TypographyText, { type: "danger", style: { display: "block", marginBottom: 16 } },
        "队列状态加载失败: " + error) : null,
      stats && React.createElement("div", { style: { marginBottom: 16 } },
        React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, flexWrap: "wrap", gap: 8 } },
          React.createElement(TypographyText, { strong: true }, "队列监控"),
          React.createElement(Space, null,
            stats.transcribe_pool_size != null && stats.transcribe_pool_size > 0
              && React.createElement(TypographyText, { type: "secondary", style: { fontSize: 12 } },
                  `转写竞争池 ${stats.transcribe_pool_size} worker`),
            React.createElement(TypographyText, { type: "secondary", style: { fontSize: 12 } }, "每 2 秒刷新"),
            stats.control?.pause_all
              ? React.createElement(Button, { size: "small", icon: React.createElement(CaretRightOutlined),
                  onClick: () => toggleAll(false) }, "全部恢复")
              : React.createElement(Button, { size: "small", danger: true, icon: React.createElement(PauseOutlined),
                  onClick: () => toggleAll(true) }, "全部暂停"),
          )),
        React.createElement(Row, { gutter: [12, 12] },
          LANE_ORDER.map((key) =>
            React.createElement(Col, { xs: 24, sm: 12, lg: 8, key },
              React.createElement(LaneCard, {
                laneKey: key,
                label: stats.labels?.[key] ?? key,
                stats: stats.queues[key],
                paused: stats.queues[key]?.enabled !== false
                  && ((stats.control?.pause_all ?? false) || (stats.control?.lanes?.[key]?.paused ?? false)),
                onPause: () => toggleLane(key, true),
                onResume: () => toggleLane(key, false),
              }),
            ),
          ),
        ),
      ),
    );
  }

  // ── LogsPage ──────────────────────────────────────────────────────
  const levelOptions = [
    { value: "", label: "全部级别" },
    { value: "INFO", label: "INFO" },
    { value: "WARN", label: "WARN" },
    { value: "ERROR", label: "ERROR" },
  ];
  const levelColors: Record<string, string> = {
    INFO: "success", WARN: "warning", ERROR: "error",
  };
  const logStepLabels: Record<string, string> = {
    extract_audio: "抽音频", transcribe: "转写", polish: "精修",
  };

  function LogsPage() {
    const [data, setData] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState(0);
    const [page, setPage] = React.useState(1);
    const [pageSize, setPageSize] = React.useState(50);
    const [levelFilter, setLevelFilter] = React.useState("");
    const [loading, setLoading] = React.useState(false);
    const [autoRefresh, setAutoRefresh] = React.useState(true);

    const load = React.useCallback(async () => {
      setLoading(true);
      try {
        const res = await listGlobalLogs(page, pageSize, levelFilter || undefined);
        setData(res.items);
        setTotal(res.total);
      } catch (e: unknown) {
        message.error("加载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setLoading(false); }
    }, [page, pageSize, levelFilter]);

    React.useEffect(() => { load(); }, [load]);
    React.useEffect(() => {
      if (!autoRefresh) return;
      const id = window.setInterval(() => load(), 3000);
      return () => window.clearInterval(id);
    }, [autoRefresh, load]);
    React.useEffect(() => { setPage(1); }, [levelFilter]);

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, flexWrap: "wrap", gap: 8 } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "全局日志"),
        React.createElement(Space, { wrap: true },
          React.createElement(Select, { value: levelFilter, options: levelOptions, style: { width: 120 }, onChange: setLevelFilter }),
          React.createElement(Button, { type: autoRefresh ? "primary" : "default",
            onClick: () => setAutoRefresh((v) => !v) }, autoRefresh ? "自动刷新开" : "自动刷新关"),
          React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: load, loading }, "刷新"),
        ),
      ),
      React.createElement(Paragraph, { type: "secondary" }, "全部处理任务的执行日志，按时间倒序；默认每 3 秒刷新。"),
      React.createElement(Table, {
        rowKey: "id", size: "small",
        columns: [
          { title: "时间", dataIndex: "created_at", width: 168, render: (v: string) => formatDateTime(v) },
          { title: "级别", dataIndex: "level", width: 80,
            render: (level: string) => React.createElement(Tag, { color: levelColors[level] || "default" }, level) },
          { title: "来源", key: "source", width: 220, ellipsis: true,
            render: (_v: any, row: any) => {
              if (!row.workflow_id) return React.createElement(TypographyText, { type: "secondary" }, "系统");
              const label = row.source_name || row.workflow_id.slice(0, 8);
              return React.createElement(TypographyText, { style: { fontSize: 13 } },
                label + (row.step_type ? ` · ${logStepLabels[row.step_type] || row.step_type}` : ""));
            } },
          { title: "消息", dataIndex: "message", ellipsis: true,
            render: (msg: string) => React.createElement("span", { style: { fontFamily: "ui-monospace, monospace", fontSize: 12 } }, msg) },
        ],
        dataSource: data, loading,
        pagination: {
          current: page, pageSize, total, showSizeChanger: true,
          pageSizeOptions: [20, 50, 100, 200],
          showTotal: (t: number, range: number[]) => total ? `第 ${range[0]}-${range[1]} 条，共 ${t} 条` : "共 0 条",
          onChange: (p: number, ps: number) => { setPage(p); setPageSize(ps); },
        },
      }));
  }

  // ── ArtifactsPage ─────────────────────────────────────────────────
  const stepFilterOptions = [
    { value: "", label: "全部类型" },
    { value: "extract_audio", label: "抽音频" },
    { value: "transcribe", label: "转写稿" },
    { value: "polish", label: "精修稿" },
  ];
  const stepColors: Record<string, string> = {
    extract_audio: "blue", transcribe: "purple", polish: "cyan",
  };

  function ArtifactsPage() {
    const [data, setData] = React.useState<any[]>([]);
    const [total, setTotal] = React.useState(0);
    const [page, setPage] = React.useState(1);
    const [pageSize, setPageSize] = React.useState(20);
    const [stepFilter, setStepFilter] = React.useState("");
    const [loading, setLoading] = React.useState(false);
    const [downloading, setDownloading] = React.useState(false);
    const [selectedKeys, setSelectedKeys] = React.useState<string[]>([]);
    const [preview, setPreview] = React.useState<any>(null);

    const load = React.useCallback(async () => {
      setLoading(true);
      try {
        const res = await listArtifacts(page, pageSize, stepFilter || undefined);
        setData(res.items);
        setTotal(res.total);
      } catch (e: unknown) {
        message.error("加载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setLoading(false); }
    }, [page, pageSize, stepFilter]);

    React.useEffect(() => { load(); }, [load]);
    React.useEffect(() => { setPage(1); }, [stepFilter]);

    const handleBatchDownload = async () => {
      if (!selectedKeys.length) return;
      setDownloading(true);
      try {
        downloadBlob(await batchDownloadArtifacts(selectedKeys), `artifacts-${selectedKeys.length}.zip`);
        message.success("已开始下载 zip");
      } catch (e: unknown) {
        message.error("下载失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setDownloading(false); }
    };

    const columns: any[] = [
      { title: "序号", key: "index", width: 72, align: "center",
        render: (_v: any, _r: any, idx: number) => (page - 1) * pageSize + idx + 1 },
      { title: "产物文件", dataIndex: "name", key: "name",
        render: (name: string, r: any) => React.createElement(Button, {
          type: "link", style: { padding: 0, height: "auto", whiteSpace: "normal", textAlign: "left" },
          onClick: () => setPreview({ fileId: r.file_id, stepType: r.step_type, fileName: r.name, downloadUrl: r.download_url }),
        }, name) },
      { title: "类型", dataIndex: "step_label", key: "step_type", width: 88,
        render: (label: string, r: any) => React.createElement(Tag, { color: stepColors[r.step_type] || "default" }, label) },
      { title: "模型 / 引擎", dataIndex: "run_model", key: "run_model", ellipsis: true,
        render: (m: string | null) => m ? React.createElement(TypographyText, { style: { fontSize: 12 } }, m) : "—" },
      { title: "耗时", dataIndex: "duration_seconds", key: "duration", width: 100,
        render: (s: number) => formatDuration(s) },
      { title: "来源任务", dataIndex: "source_name", key: "source", ellipsis: true,
        render: (name: string) => React.createElement(TypographyText, null, name) },
      { title: "大小", dataIndex: "size_bytes", key: "size", width: 100, render: formatSize },
      { title: "完成时间", dataIndex: "completed_at", key: "completed_at", width: 180,
        render: (t: string) => t ? formatDateTime(t) : "—" },
      { title: "操作", key: "actions", width: 120,
        render: (_: any, r: any) => React.createElement(Space, { size: "small" },
          React.createElement(Button, { type: "link", size: "small", icon: React.createElement(EyeOutlined),
            onClick: () => setPreview({ fileId: r.file_id, stepType: r.step_type, fileName: r.name, downloadUrl: r.download_url }) }, "预览"),
          React.createElement(Button, { type: "link", size: "small", icon: React.createElement(DownloadOutlined),
            href: getFileDownloadUrl(r.file_id, { stepType: r.step_type, downloadUrl: r.download_url }),
            target: "_blank" }, "下载"),
        ),
      },
    ];

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 12 } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "产物文件"),
        React.createElement(Space, { wrap: true },
          selectedKeys.length > 0 && React.createElement(React.Fragment, null,
            React.createElement(TypographyText, { type: "secondary" }, `已选 ${selectedKeys.length} 项`),
            React.createElement(Button, { type: "primary", icon: React.createElement(DownloadOutlined),
              loading: downloading, onClick: handleBatchDownload }, "批量下载"),
          ),
          React.createElement(Select, { value: stepFilter, options: stepFilterOptions, style: { width: 140 }, onChange: setStepFilter }),
          React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: load, disabled: loading }, "刷新"),
        ),
      ),
      React.createElement(Table, {
        rowKey: "file_id", size: "small",
        rowSelection: { selectedRowKeys: selectedKeys, onChange: (keys: any) => setSelectedKeys(keys) },
        columns, dataSource: data, loading,
        pagination: {
          current: page, pageSize, total, showSizeChanger: true,
          pageSizeOptions: [10, 20, 50, 100],
          showTotal: (t: number, range: number[]) => total ? `第 ${range[0]}-${range[1]} 条，共 ${t} 条` : "共 0 条",
          onChange: (p: number, ps: number) => { setPage(p); setPageSize(ps); },
        },
      }),
      React.createElement(ArtifactPreviewModal, { target: preview, onClose: () => setPreview(null) }));
  }

  // ── SettingsPage ──────────────────────────────────────────────────
  const BACKEND_OPTIONS = [
    { value: "local", label: "本地 Whisper" },
    { value: "openai", label: "OpenAI 兼容 API" },
    { value: "dashscope", label: "阿里云 DashScope" },
  ];
  const LANE_ICONS: Record<string, React.ReactNode> = {
    fast: React.createElement(ThunderboltOutlined),
    slow: React.createElement(HourglassOutlined),
    external: React.createElement(CloudOutlined),
  };
  const LANE_FIXED_DEVICE: Record<string, { value: string; label: string }> = {
    fast: { value: "cuda", label: "CUDA（GPU）" },
    slow: { value: "cpu", label: "CPU" },
  };

  function LaneStatusTag({ lane }: { lane: any }) {
    if (!lane.enabled) return React.createElement(Tag, null, "已关闭");
    if (lane.available) return React.createElement(Tag, { color: "success", icon: React.createElement(CheckCircleOutlined) }, "可路由");
    if (lane.configured) return React.createElement(Tag, { color: "warning" }, "未就绪");
    return React.createElement(Tag, { color: "error", icon: React.createElement(CloseCircleOutlined) }, "未配置");
  }

  function TranscribeLaneCard({ laneKey, lane, localModelOptions, form }: {
    laneKey: "fast" | "slow" | "external";
    lane: any;
    localModelOptions: any[];
    form: any;
  }) {
    const backend = Form.useWatch(`${laneKey}_backend`, form);
    const enabled = Form.useWatch(`${laneKey}_enabled`, form);
    const isLocal = backend === "local";
    const isOpenai = backend === "openai";
    const isDashscope = backend === "dashscope";

    return React.createElement(Card, {
      size: "small",
      style: { marginBottom: 16, opacity: enabled ? 1 : 0.65 },
      title: React.createElement(Space, null, LANE_ICONS[laneKey], React.createElement("span", null, lane.label), React.createElement(LaneStatusTag, { lane })),
      extra: React.createElement(Form.Item, { name: `${laneKey}_enabled`, valuePropName: "checked", noStyle: true },
        React.createElement(Switch, { checkedChildren: "启用", unCheckedChildren: "关闭" })),
    },
      React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginBottom: 12 } },
        lane.reason, !lane.available && lane.enabled ? " — 未配置完成前不会路由任务到此队列。" : null),
      React.createElement(Form.Item, { name: `${laneKey}_backend`, label: "后端类型" },
        React.createElement(Select, { options: BACKEND_OPTIONS, disabled: !enabled })),
      laneKey !== "external" && isLocal && enabled && React.createElement(React.Fragment, null,
        localModelOptions.length === 0
          ? React.createElement(Alert, { type: "warning", showIcon: true, style: { marginBottom: 12 },
              message: "~/.cache/qwenpaw/models/ 目录下暂无已下载模型",
              description: "执行：uv run python scripts/download_whisper_model.py small" })
          : null,
        React.createElement(Form.Item, { name: `${laneKey === "fast" ? "transcribe_fast_model_path" : "transcribe_slow_model_path"}`, label: "模型" },
          React.createElement(Select, { options: localModelOptions, placeholder: "请先下载模型到 ~/.cache/qwenpaw/models/",
            disabled: localModelOptions.length === 0 })),
        React.createElement(Form.Item, { name: `${laneKey === "fast" ? "transcribe_fast_device" : "transcribe_slow_device"}`, hidden: true, initialValue: LANE_FIXED_DEVICE[laneKey].value },
          React.createElement(Input, null)),
        React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginBottom: 12 } },
          `设备：${LANE_FIXED_DEVICE[laneKey].label}（${laneKey}队列固定）`),
      ),
      laneKey === "external" && isOpenai && enabled && React.createElement(React.Fragment, null,
        lane.openai_api_key_set
          ? React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginBottom: 8 } },
              `当前 Key：${lane.openai_api_key_masked || "已设置"}`)
          : null,
        React.createElement(Form.Item, { name: "transcribe_openai_api_key", label: "OpenAI API Key" },
          React.createElement(Input.Password, { placeholder: "留空表示不修改", autoComplete: "new-password" })),
        React.createElement(Row, { gutter: 12 },
          React.createElement(Col, { span: 14 },
            React.createElement(Form.Item, { name: "transcribe_openai_base_url", label: "Base URL" },
              React.createElement(Input, null))),
          React.createElement(Col, { span: 10 },
            React.createElement(Form.Item, { name: "transcribe_openai_model", label: "模型" },
              React.createElement(Input, null))),
        ),
      ),
      laneKey === "external" && isDashscope && enabled && React.createElement(React.Fragment, null,
        lane.dashscope_api_key_set
          ? React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginBottom: 8 } },
              `当前 Key：${lane.dashscope_api_key_masked || "已设置"}`)
          : null,
        React.createElement(Form.Item, { name: "dashscope_api_key", label: "DashScope API Key" },
          React.createElement(Input.Password, { placeholder: "留空表示不修改", autoComplete: "new-password" })),
        React.createElement(Row, { gutter: 12 },
          React.createElement(Col, { span: 14 },
            React.createElement(Form.Item, { name: "dashscope_base_url", label: "兼容模式 URL" },
              React.createElement(Input, null))),
          React.createElement(Col, { span: 10 },
            React.createElement(Form.Item, { name: "dashscope_asr_model", label: "ASR 模型" },
              React.createElement(Input, { placeholder: "paraformer-v2" }))),
        ),
      ),
      React.createElement(Form.Item, { name: `${laneKey}_max_concurrent`, label: "并发 worker 数" },
        React.createElement(InputNumber, { min: 0, max: 32, style: { width: 120 }, disabled: !enabled })),
    );
  }

  const LANE_ORDER_SETTINGS = ["fast", "slow", "external"] as const;

  function SettingsPage() {
    const [form] = Form.useForm();
    const [loading, setLoading] = React.useState(true);
    const [saving, setSaving] = React.useState(false);
    const [meta, setMeta] = React.useState<any>(null);
    const fastEnabled = Form.useWatch("fast_enabled", form);
    const slowEnabled = Form.useWatch("slow_enabled", form);
    const externalEnabled = Form.useWatch("external_enabled", form);
    const defaultLane = Form.useWatch("transcribe_default_lane", form);

    const laneSwitchOn = (lane: string) => {
      const v = { fast: fastEnabled, slow: slowEnabled, external: externalEnabled }[lane];
      return v !== false;
    };

    React.useEffect(() => {
      if (!defaultLane || laneSwitchOn(defaultLane)) return;
      const next = LANE_ORDER_SETTINGS.find((l) => laneSwitchOn(l));
      if (next) form.setFieldsValue({ transcribe_default_lane: next });
    }, [defaultLane, fastEnabled, slowEnabled, externalEnabled]);

    const load = React.useCallback(async () => {
      setLoading(true);
      try {
        const cfg = await getProcessorConfig();
        setMeta(cfg);
        const values: Record<string, unknown> = {
          minimax_api_key: "",
          transcribe_openai_api_key: "",
          dashscope_api_key: "",
          transcribe_default_lane: cfg.transcribe_default_lane,
        };
        for (const lane of cfg.transcribe_lanes || []) {
          values[`${lane.lane}_enabled`] = lane.enabled;
          values[`${lane.lane}_backend`] = lane.backend;
          if (lane.lane === "fast") {
            values.transcribe_fast_model_path = lane.model_path || (cfg.available_local_models?.[0]?.value ?? "");
            values.transcribe_fast_device = LANE_FIXED_DEVICE.fast.value;
          }
          if (lane.lane === "slow") {
            values.transcribe_slow_model_path = lane.model_path || (cfg.available_local_models?.[0]?.value ?? "");
            values.transcribe_slow_device = LANE_FIXED_DEVICE.slow.value;
          }
          if (lane.backend === "openai") {
            values.transcribe_openai_base_url = lane.openai_base_url ?? "";
            values.transcribe_openai_model = lane.openai_model ?? "whisper-1";
          }
          if (lane.backend === "dashscope") {
            values.dashscope_base_url = lane.dashscope_base_url ?? "";
            values.dashscope_asr_model = lane.dashscope_model ?? "paraformer-v2";
          }
          values[`${lane.lane}_max_concurrent`] = lane.max_concurrent ?? 1;
        }
        form.setFieldsValue(values);
      } catch (e: unknown) {
        message.error("加载配置失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setLoading(false); }
    }, [form]);

    React.useEffect(() => { load(); }, [load]);

    const onSave = async () => {
      const v = await form.validateFields();
      const body: Record<string, unknown> = {};
      if (v.minimax_api_key?.trim()) body.minimax_api_key = v.minimax_api_key.trim();
      if (v.transcribe_openai_api_key?.trim()) body.transcribe_openai_api_key = v.transcribe_openai_api_key.trim();
      if (v.dashscope_api_key?.trim()) body.dashscope_api_key = v.dashscope_api_key.trim();

      const pickDefaultLane = () => {
        const pref = v.transcribe_default_lane as string | undefined;
        if (pref && v[`${pref}_enabled`] !== false) return pref;
        return LANE_ORDER_SETTINGS.find((l) => v[`${l}_enabled`] !== false) ?? pref;
      };
      body.transcribe_default_lane = pickDefaultLane();
      body.transcribe_fast_enabled = v.fast_enabled;
      body.transcribe_slow_enabled = v.slow_enabled;
      body.transcribe_external_enabled = v.external_enabled;
      body.transcribe_fast_backend = v.fast_backend;
      body.transcribe_slow_backend = v.slow_backend;
      body.transcribe_external_backend = v.external_backend;

      if (v.fast_enabled && v.fast_backend === "local") {
        body.transcribe_fast_model_path = v.transcribe_fast_model_path;
        body.transcribe_fast_device = LANE_FIXED_DEVICE.fast.value;
      }
      if (v.slow_enabled && v.slow_backend === "local") {
        body.transcribe_slow_model_path = v.transcribe_slow_model_path;
        body.transcribe_slow_device = LANE_FIXED_DEVICE.slow.value;
      }

      if (v.transcribe_openai_base_url) body.transcribe_openai_base_url = v.transcribe_openai_base_url;
      if (v.transcribe_openai_model) body.transcribe_openai_model = v.transcribe_openai_model;
      if (v.dashscope_base_url) body.dashscope_base_url = v.dashscope_base_url;
      if (v.dashscope_asr_model) body.dashscope_asr_model = v.dashscope_asr_model;

      if (v.fast_max_concurrent != null) body.max_concurrent_transcribe_fast = v.fast_max_concurrent;
      if (v.slow_max_concurrent != null) body.max_concurrent_transcribe_slow = v.slow_max_concurrent;
      if (v.external_max_concurrent != null) body.max_concurrent_transcribe_external = v.external_max_concurrent;

      setSaving(true);
      try {
        const cfg = await updateProcessorConfig(body);
        setMeta(cfg);
        form.setFieldsValue({
          minimax_api_key: "",
          transcribe_openai_api_key: "",
          dashscope_api_key: "",
        });
        message.success(`配置已保存并生效（转写竞争池 ${cfg.transcribe_pool_size} worker）`);
        await load();
      } catch (e: unknown) {
        message.error("保存失败: " + (e instanceof Error ? e.message : String(e)));
      } finally { setSaving(false); }
    };

    const lanes = meta?.transcribe_lanes ?? [];
    const laneByKey = (k: string) => lanes.find((l: any) => l.lane === k);
    const available = meta?.available_transcribe_lanes ?? [];

    return React.createElement("div", null,
      React.createElement("div", { style: { display: "flex", justifyContent: "space-between", marginBottom: 16 } },
        React.createElement(Title, { level: 4, style: { margin: 0 } }, "配置管理"),
        React.createElement(Button, { icon: React.createElement(ReloadOutlined), onClick: load, disabled: loading }, "刷新"),
      ),
      React.createElement(Alert, {
        type: "info", showIcon: true, style: { marginBottom: 16 },
        message: "内部动态路由（上传 API 无需改）",
        description: React.createElement("span", null,
          "快/慢/云端任务进入",
          React.createElement("strong", null, "同一条转写队列"),
          `，${meta?.transcribe_pool_size ?? 1} 个 worker `,
          React.createElement("strong", null, "竞争消费"),
          "（总数 = 快+慢+云端并发配置之和）。执行时仍按任务绑定的 GPU/CPU/API 后端。上传 API 不变。",
          meta?.config_reload_hint ? ` ${meta.config_reload_hint}` : "",
          available.length > 0
            ? React.createElement("div", { style: { marginTop: 8 } },
                "当前可路由队列：", React.createElement(Tag, { color: "blue" }, available.join(" · ")))
            : React.createElement("div", { style: { marginTop: 8, color: "#cf1322" } },
                "当前没有可用转写队列，上传音视频将无法创建转写任务。"),
        ),
      }),
      React.createElement(Form, { form, layout: "vertical", disabled: loading },
        React.createElement(Card, { title: "默认转写队列", style: { marginBottom: 16 } },
          React.createElement(Form.Item, {
            name: "transcribe_default_lane", label: "新建任务未指定队列时使用",
            extra: meta && !meta.default_lane_available
              ? React.createElement(TypographyText, { type: "danger" }, "当前默认值不可用，将自动落到第一个可用队列")
              : null,
          },
            React.createElement(Select, {
              options: (lanes || []).map((l: any) => {
                const ok = laneSwitchOn(l.lane) && l.available;
                return { value: l.lane, label: `${l.label}${ok ? "" : "（不可用）"}`, disabled: !ok };
              }),
            }),
          ),
        ),
        React.createElement(Title, { level: 5 }, "转写队列"),
        laneByKey("fast") && React.createElement(TranscribeLaneCard, {
          laneKey: "fast", lane: laneByKey("fast"), form,
          localModelOptions: meta?.available_local_models ?? [],
        }),
        laneByKey("slow") && React.createElement(TranscribeLaneCard, {
          laneKey: "slow", lane: laneByKey("slow"), form,
          localModelOptions: meta?.available_local_models ?? [],
        }),
        laneByKey("external") && React.createElement(TranscribeLaneCard, {
          laneKey: "external", lane: laneByKey("external"), form,
          localModelOptions: [],
        }),
        React.createElement(Divider, null),
        React.createElement(Card, { title: "MiniMax（文本精修）", style: { marginBottom: 16 } },
          meta?.minimax_api_key_set
            ? React.createElement(TypographyText, { type: "secondary", style: { display: "block", marginBottom: 12 } },
                `当前已配置：${meta.minimax_api_key_masked || "（已设置）"}`)
            : null,
          React.createElement(Form.Item, { name: "minimax_api_key", label: "API Key", extra: "留空表示不修改" },
            React.createElement(Input.Password, { placeholder: "MiniMax API Key", autoComplete: "new-password" })),
        ),
        React.createElement(Tooltip, { title: "保存写入 .env 并热加载转写后端" },
          React.createElement(Button, { type: "primary", icon: React.createElement(SaveOutlined),
            loading: saving, onClick: onSave }, "保存全部配置"),
        ),
      ),
    );
  }

  // ── PluginPage (root) ─────────────────────────────────────────────
  function PluginPage() {
    const [tab, setTab] = React.useState("files");
    const [detailId, setDetailId] = React.useState<string | null>(null);
    const [resultsId, setResultsId] = React.useState<string | null>(null);

    const tabs = [
      { id: "files", label: "任务管理" },
      { id: "queues", label: "队列" },
      { id: "logs", label: "日志" },
      { id: "artifacts", label: "产物" },
      { id: "settings", label: "设置" },
    ];

    // Show workflow detail or file results (overrides normal tab content)
    if (detailId) {
      return React.createElement(Space, { direction: "vertical", size: "large", style: { width: "100%" } },
        React.createElement("div", { style: { padding: "24px 24px 0 24px" } },
          React.createElement(Title, { level: 3, style: { marginBottom: 16 } }, "Media Studio")),
        React.createElement("div", { style: { padding: "0 24px 24px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" } },
          React.createElement(WorkflowStatusPage, {
            workflowId: detailId,
            onBack: () => setDetailId(null),
            onViewResults: (id: string) => { setDetailId(null); setResultsId(id); },
          }),
        ),
      );
    }

    if (resultsId) {
      return React.createElement(Space, { direction: "vertical", size: "large", style: { width: "100%" } },
        React.createElement("div", { style: { padding: "24px 24px 0 24px" } },
          React.createElement(Title, { level: 3, style: { marginBottom: 16 } }, "Media Studio")),
        React.createElement("div", { style: { padding: "0 24px 24px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" } },
          React.createElement(FileResultsPage, { workflowId: resultsId, onBack: () => setResultsId(null) }),
        ),
      );
    }

    const content = (() => {
      switch (tab) {
        case "queues": return React.createElement(QueuePage);
        case "logs": return React.createElement(LogsPage);
        case "artifacts": return React.createElement(ArtifactsPage);
        case "settings": return React.createElement(SettingsPage);
        default: return React.createElement(FileListPage, { onViewDetail: (id: string) => setDetailId(id) });
      }
    })();

    return React.createElement(Space, { direction: "vertical", size: "large", style: { width: "100%" } },
      React.createElement("div", { style: { padding: "24px 24px 0 24px" } },
        React.createElement(Title, { level: 3, style: { marginBottom: 16 } }, "Media Studio"),
        React.createElement("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } },
          tabs.map((t) =>
            React.createElement(Button, {
              key: t.id,
              type: tab === t.id ? "primary" : "default",
              onClick: () => { setTab(t.id); setDetailId(null); setResultsId(null); },
            }, t.label),
          ),
        ),
      ),
      React.createElement("div", { style: { padding: "0 24px 24px 24px", maxWidth: 1200, margin: "0 auto", width: "100%" } },
        content,
      ),
    );
  }

  // ── Register ──────────────────────────────────────────────────────
  window.QwenPaw.registerRoutes?.("media-studio", [
    {
      path: "/plugin/media-studio",
      component: PluginPage,
      label: "Media Studio",
      icon: "⚙️",
      priority: 10,
    },
  ]);
})();
