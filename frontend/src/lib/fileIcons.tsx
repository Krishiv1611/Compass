import type { ReactNode } from "react";
import { Folder, FolderOpen, Image as ImageIcon, FileText } from "lucide-react";

export type FileType =
  | "typescript"
  | "javascript"
  | "python"
  | "css"
  | "html"
  | "json"
  | "markdown"
  | "shell"
  | "image"
  | "default";

export const FILE_TYPE_COLORS: Record<FileType | "folder", string> = {
  typescript: "#3178C6",
  javascript: "#F7DF1E",
  python: "#3776AB",
  css: "#38BDF8",
  html: "#E34F26",
  json: "#F59E0B",
  markdown: "#14B8A6",
  shell: "#A855F7",
  image: "#10B981",
  default: "#94A3B8",
  folder: "#EAB308", // warm amber/gold
};

export function getFileType(filename: string): FileType {
  const lower = filename.toLowerCase().trim();

  // Exact names or prefixes
  if (
    lower === ".env" ||
    lower.startsWith(".env.") ||
    lower === "dockerfile" ||
    lower.startsWith("dockerfile.") ||
    lower === "makefile" ||
    lower === ".gitignore" ||
    lower === ".editorconfig"
  ) {
    return "shell";
  }

  const ext = lower.includes(".") ? lower.slice(lower.lastIndexOf(".")) : "";

  switch (ext) {
    case ".ts":
    case ".tsx":
    case ".mts":
    case ".cts":
      return "typescript";
    case ".js":
    case ".jsx":
    case ".mjs":
    case ".cjs":
      return "javascript";
    case ".py":
    case ".pyw":
      return "python";
    case ".css":
    case ".scss":
    case ".sass":
    case ".less":
      return "css";
    case ".html":
    case ".htm":
      return "html";
    case ".json":
    case ".json5":
    case ".jsonc":
      return "json";
    case ".md":
    case ".mdx":
      return "markdown";
    case ".sh":
    case ".bash":
    case ".zsh":
    case ".yml":
    case ".yaml":
    case ".toml":
    case ".ini":
    case ".conf":
      return "shell";
    case ".png":
    case ".jpg":
    case ".jpeg":
    case ".gif":
    case ".svg":
    case ".webp":
    case ".ico":
      return "image";
    default:
      return "default";
  }
}

export function getFileColor(filename: string, isFolder?: boolean): string {
  if (isFolder) return FILE_TYPE_COLORS.folder;
  const type = getFileType(filename);
  return FILE_TYPE_COLORS[type];
}

export function getFileIcon(
  name: string,
  isFolder?: boolean,
  isOpen?: boolean,
  className = "h-4 w-4 shrink-0"
): ReactNode {
  if (isFolder) {
    if (isOpen) {
      return (
        <FolderOpen
          data-testid="folder-icon-open"
          aria-label="Open folder"
          className={`${className} text-amber-500 fill-amber-500/25`}
        />
      );
    }
    return (
      <Folder
        data-testid="folder-icon-closed"
        aria-label="Folder"
        className={`${className} text-amber-500 fill-amber-500/20`}
      />
    );
  }

  const type = getFileType(name);

  switch (type) {
    case "typescript":
      return (
        <svg
          data-testid="file-icon-typescript"
          aria-label="TypeScript file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#3178C6" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fill="#FFFFFF"
            fontSize="8"
            fontWeight="bold"
            fontFamily="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
          >
            TS
          </text>
        </svg>
      );

    case "javascript":
      return (
        <svg
          data-testid="file-icon-javascript"
          aria-label="JavaScript file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#F7DF1E" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fill="#000000"
            fontSize="8"
            fontWeight="bold"
            fontFamily="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
          >
            JS
          </text>
        </svg>
      );

    case "python":
      return (
        <svg
          data-testid="file-icon-python"
          aria-label="Python file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M7.9 2.5c-2.6 0-2.4 1.1-2.4 1.1l.01 1.2h2.4v.3H4.5s-1.5-.2-1.5 2.4c0 2.6 1.3 2.5 1.3 2.5h.8V8.8s-.04-1.4 1.4-1.4h2.3s1.3.02 1.3-1.3V4.9s.18-2.4-2.4-2.4zm-.7.8a.5.5 0 110 1 .5.5 0 010-1z"
            fill="#3776AB"
          />
          <path
            d="M8.1 13.5c2.6 0 2.4-1.1 2.4-1.1l-.01-1.2H8.1v-.3h3.4s1.5.2 1.5-2.4c0-2.6-1.3-2.5-1.3-2.5h-.8v1.2s.04 1.4-1.4 1.4H7.2s-1.3-.02-1.3 1.3v1.9s-.18 2.4 2.4 2.4zm.7-.8a.5.5 0 110-1 .5.5 0 010 1z"
            fill="#FFD43B"
          />
        </svg>
      );

    case "css":
      return (
        <svg
          data-testid="file-icon-css"
          aria-label="CSS file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#38BDF8" fillOpacity="0.16" stroke="#38BDF8" strokeWidth="1" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fill="#38BDF8"
            fontSize="9"
            fontWeight="bold"
            fontFamily="system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
          >
            #
          </text>
        </svg>
      );

    case "html":
      return (
        <svg
          data-testid="file-icon-html"
          aria-label="HTML file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#E34F26" fillOpacity="0.16" stroke="#E34F26" strokeWidth="1" />
          <text
            x="8"
            y="11"
            textAnchor="middle"
            fill="#E34F26"
            fontSize="7"
            fontWeight="bold"
            fontFamily="monospace"
          >
            &lt;&gt;
          </text>
        </svg>
      );

    case "json":
      return (
        <svg
          data-testid="file-icon-json"
          aria-label="JSON file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#F59E0B" fillOpacity="0.16" stroke="#F59E0B" strokeWidth="1" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fill="#F59E0B"
            fontSize="8"
            fontWeight="bold"
            fontFamily="monospace"
          >
            {"{}"}
          </text>
        </svg>
      );

    case "markdown":
      return (
        <svg
          data-testid="file-icon-markdown"
          aria-label="Markdown file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#14B8A6" fillOpacity="0.16" stroke="#14B8A6" strokeWidth="1" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fill="#14B8A6"
            fontSize="8"
            fontWeight="bold"
            fontFamily="monospace"
          >
            M↓
          </text>
        </svg>
      );

    case "shell":
      return (
        <svg
          data-testid="file-icon-shell"
          aria-label="Shell or config file"
          viewBox="0 0 16 16"
          className={className}
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect width="16" height="16" rx="2.5" fill="#A855F7" fillOpacity="0.16" stroke="#A855F7" strokeWidth="1" />
          <text
            x="8"
            y="11"
            textAnchor="middle"
            fill="#A855F7"
            fontSize="7"
            fontWeight="bold"
            fontFamily="monospace"
          >
            &gt;_
          </text>
        </svg>
      );

    case "image":
      return (
        <ImageIcon
          data-testid="file-icon-image"
          aria-label="Image file"
          className={`${className} text-emerald-400`}
        />
      );

    default:
      return (
        <FileText
          data-testid="file-icon-default"
          aria-label="File"
          className={`${className} text-muted-foreground/80`}
        />
      );
  }
}
