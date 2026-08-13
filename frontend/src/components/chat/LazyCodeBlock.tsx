import { useEffect, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";

type LoadedHighlighter = {
  Component: typeof import("react-syntax-highlighter/dist/esm/prism-light").default;
  light: Record<string, React.CSSProperties>;
  dark: Record<string, React.CSSProperties>;
};

let cached: LoadedHighlighter | null = null;
let loading: Promise<LoadedHighlighter> | null = null;
const aliases: Record<string, string> = { sh: "bash", shell: "bash", js: "javascript", md: "markdown", py: "python", ts: "typescript", xml: "html" };
const supported = new Set(["bash", "css", "html", "javascript", "json", "markdown", "python", "typescript"]);

const loadHighlighter = () => {
  if (cached) return Promise.resolve(cached);
  loading ||= Promise.all([
    import("react-syntax-highlighter/dist/esm/prism-light"),
    import("react-syntax-highlighter/dist/esm/styles/prism/one-light"),
    import("react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus"),
    import("react-syntax-highlighter/dist/esm/languages/prism/bash"),
    import("react-syntax-highlighter/dist/esm/languages/prism/css"),
    import("react-syntax-highlighter/dist/esm/languages/prism/markup"),
    import("react-syntax-highlighter/dist/esm/languages/prism/javascript"),
    import("react-syntax-highlighter/dist/esm/languages/prism/json"),
    import("react-syntax-highlighter/dist/esm/languages/prism/markdown"),
    import("react-syntax-highlighter/dist/esm/languages/prism/python"),
    import("react-syntax-highlighter/dist/esm/languages/prism/typescript"),
  ]).then(([highlighter, oneLight, vscDarkPlus, bash, css, markup, javascript, json, markdown, python, typescript]) => {
    const Component = highlighter.default;
    Component.registerLanguage("bash", bash.default);
    Component.registerLanguage("css", css.default);
    Component.registerLanguage("html", markup.default);
    Component.registerLanguage("javascript", javascript.default);
    Component.registerLanguage("json", json.default);
    Component.registerLanguage("markdown", markdown.default);
    Component.registerLanguage("python", python.default);
    Component.registerLanguage("typescript", typescript.default);
    cached = {
      Component,
      light: oneLight.default,
      dark: vscDarkPlus.default,
    };
    return cached;
  });
  return loading;
};

export default function LazyCodeBlock({ language, code }: { language: string; code: string }) {
  const { resolvedTheme } = useTheme();
  const [loaded, setLoaded] = useState<LoadedHighlighter | null>(cached);

  useEffect(() => {
    let active = true;
    void loadHighlighter().then((value) => { if (active) setLoaded(value); });
    return () => { active = false; };
  }, []);

  if (!loaded) {
    return <pre className="m-0 overflow-auto bg-muted/40 p-4 font-mono text-[13px] leading-5"><code>{code}</code></pre>;
  }

  const SyntaxHighlighter = loaded.Component;
  const normalized = aliases[language.toLowerCase()] ?? language.toLowerCase();
  const highlightedLanguage = supported.has(normalized) ? normalized : "text";
  return <SyntaxHighlighter PreTag="div" language={highlightedLanguage} style={resolvedTheme === "dark" ? loaded.dark : loaded.light} customStyle={{ margin: 0, padding: "1rem", fontSize: "13px", lineHeight: "20px" }}>{code}</SyntaxHighlighter>;
}
