// 数字与时间格式化工具。

/** 取本地时区的 YYYY-MM-DD(避开 toISOString 的 UTC 偏移问题)。 */
export function localDateString(d: Date = new Date()): string {
  return (
    d.getFullYear() +
    "-" +
    String(d.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(d.getDate()).padStart(2, "0")
  );
}

export function formatNumber(num: number): string {
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + "k";
  }
  return num.toString();
}

export function formatStarsDelta(delta: number): string {
  if (delta > 0) return "+" + formatNumber(delta) + " ↑";
  if (delta < 0) return formatNumber(delta) + " ↓";
  return "—";
}

export function getTimeAgo(time: string): string {
  const now = new Date();
  const date = new Date(time);
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return Math.floor(diff / 60) + "分钟前";
  if (diff < 86400) return Math.floor(diff / 3600) + "小时前";
  return Math.floor(diff / 86400) + "天前";
}

export const LANGUAGES = [
  { value: "all", label: "全部语言" },
  { value: "python", label: "Python" },
  { value: "javascript", label: "JavaScript" },
  { value: "typescript", label: "TypeScript" },
  { value: "rust", label: "Rust" },
  { value: "go", label: "Go" },
  { value: "java", label: "Java" },
  { value: "html", label: "HTML" },
] as const;
