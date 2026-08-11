import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import LazyCodeBlock from "./LazyCodeBlock";

export default function MarkdownMessage({ content, isStreaming }: { content: string; isStreaming?: boolean }) {
  const components: Components = {
    code({ children, className, node: _node, ref: _ref, ...props }) {
      const language = /language-(\w+)/.exec(className || "")?.[1];
      if (language) return <div className="my-3 overflow-hidden rounded-md border border-border"><div className="border-b border-border px-3 py-1.5 font-mono text-xs text-muted-foreground">{language}</div><LazyCodeBlock language={language} code={String(children).replace(/\n$/, "")} /></div>;
      return <code {...props} className={`${className || ""} rounded-sm bg-muted px-1 py-0.5 font-mono text-[0.9em]`}>{children}</code>;
    },
    a({ children, ...props }) { return <a {...props} target="_blank" rel="noopener noreferrer" className="font-medium text-primary hover:underline">{children}</a>; },
  };
  return <div className="prose prose-sm max-w-none text-foreground dark:prose-invert prose-p:leading-6 prose-pre:bg-transparent prose-pre:p-0"><ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>{content}</ReactMarkdown>{isStreaming && <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" />}</div>;
}
