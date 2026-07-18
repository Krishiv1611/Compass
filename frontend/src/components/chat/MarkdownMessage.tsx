import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface MarkdownMessageProps {
  content: string;
  isStreaming?: boolean;
}

export default function MarkdownMessage({ content, isStreaming }: MarkdownMessageProps) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-6 prose-pre:p-0 prose-pre:bg-transparent">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code(props: any) {
            const { children, className, ...rest } = props;
            const match = /language-(\w+)/.exec(className || "");
            const isInline = !match && !className?.includes("language-");

            if (!isInline && match) {
              return (
                <div className="rounded-md overflow-hidden my-3 bg-[#1e1e1e] border border-border/50">
                  <div className="flex items-center justify-between px-3 py-1.5 bg-muted/30 text-xs text-muted-foreground border-b border-border/50">
                    <span>{match[1]}</span>
                  </div>
                  <SyntaxHighlighter
                    {...rest}
                    PreTag="div"
                    language={match[1]}
                    style={vscDarkPlus}
                    customStyle={{
                      margin: 0,
                      background: "transparent",
                      padding: "1rem",
                      fontSize: "0.85rem",
                    }}
                  >
                    {String(children).replace(/\n$/, "")}
                  </SyntaxHighlighter>
                </div>
              );
            }
            return (
              <code {...rest} className={`${className || ""} bg-muted/50 px-1.5 py-0.5 rounded-md text-[0.85em] font-mono`}>
                {children}
              </code>
            );
          },
          a(props: any) {
            return (
              <a {...props} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline font-medium">
                {props.children}
              </a>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="inline-block w-2 h-4 bg-primary ml-1 animate-pulse align-middle" />}
    </div>
  );
}
