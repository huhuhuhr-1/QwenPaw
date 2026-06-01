// 暗色主题 CSS 变量(注入到 .gh-trending-root)
// 配色参考 github-data-fetch

export const ROOT_CLASS = "gh-trending-root";

export const THEME_CSS = `
.${ROOT_CLASS} {
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
.${ROOT_CLASS} *,
.${ROOT_CLASS} *::before,
.${ROOT_CLASS} *::after { box-sizing: border-box; }
.${ROOT_CLASS} .gh-card {
  background: var(--gh-card);
  border: 1px solid var(--gh-border);
  border-radius: var(--gh-radius-lg);
  padding: 16px;
  transition: border-color 0.15s;
}
.${ROOT_CLASS} .gh-card:hover { border-color: var(--gh-border-hover); }
.${ROOT_CLASS} .gh-text-secondary { color: var(--gh-text-secondary); }
.${ROOT_CLASS} .gh-text-tertiary { color: var(--gh-text-tertiary); }
.${ROOT_CLASS} .gh-accent { color: var(--gh-accent); }
.${ROOT_CLASS} .gh-row {
  display: flex; align-items: center; gap: 12px;
}
.${ROOT_CLASS} .gh-table { width: 100%; border-collapse: collapse; }
.${ROOT_CLASS} .gh-table th {
  text-align: left; padding: 10px 12px;
  font-size: 0.75rem; font-weight: 500;
  color: var(--gh-text-tertiary);
  background: var(--gh-elevated);
  border-bottom: 1px solid var(--gh-border);
}
.${ROOT_CLASS} .gh-table td {
  padding: 10px 12px; font-size: 0.85rem;
  border-bottom: 1px solid var(--gh-border);
  color: var(--gh-text);
}
.${ROOT_CLASS} .gh-table tr:hover td { background: var(--gh-card-hover); cursor: pointer; }
.${ROOT_CLASS} .gh-button {
  background: var(--gh-elevated);
  border: 1px solid var(--gh-border);
  color: var(--gh-text);
  padding: 6px 14px;
  border-radius: var(--gh-radius-sm);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}
.${ROOT_CLASS} .gh-button:hover { border-color: var(--gh-accent); color: var(--gh-accent); }
.${ROOT_CLASS} .gh-button-primary {
  background: var(--gh-accent);
  border-color: var(--gh-accent);
  color: #0A0D14;
  font-weight: 600;
}
.${ROOT_CLASS} .gh-button-primary:hover { background: var(--gh-accent-hover); }
.${ROOT_CLASS} .gh-tag {
  display: inline-block; padding: 2px 8px;
  border-radius: 12px; font-size: 0.7rem;
  background: var(--gh-elevated);
  color: var(--gh-text-secondary);
  border: 1px solid var(--gh-border);
}
.${ROOT_CLASS} .gh-tag-accent { color: var(--gh-accent); border-color: var(--gh-accent); }
.${ROOT_CLASS} .gh-tag-warning { color: var(--gh-warning); border-color: var(--gh-warning); }
.${ROOT_CLASS} .gh-tag-purple { color: var(--gh-purple); border-color: var(--gh-purple); }
.${ROOT_CLASS} .gh-tag-blue { color: var(--gh-blue); border-color: var(--gh-blue); }
.${ROOT_CLASS} h1, h2, h3, h4, h5 { color: var(--gh-text); margin: 0; }
.${ROOT_CLASS} a { color: var(--gh-accent); }
`;
