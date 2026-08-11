import { useEffect, useState } from "react";
import { useTheme } from "@/components/ThemeProvider";

type LoadedHighlighter = {
  Component: typeof import("react-syntax-highlighter").Prism;
  light: Record<string, React.CSSProperties>;
  dark: Record<string, React.CSSProperties>;
};

let cached: LoadedHighlighter | null = null;
let loading: Promise<LoadedHighlighter> | null = null;

const loadHighlighter = () => {
  if (cached) return Promise.resolve(cached);
  loading ||= Promise.all([
    import("react-syntax-highlighter"),
    import("react-syntax-highlighter/dist/esm/styles/prism"),
  ]).then(([highlighter, styles]) => {
    cached = {
      Component: highlighter.Prism,
      light: styles.oneLight,
      dark: styles.vscDarkPlus,
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
  return <SyntaxHighlighter PreTag="div" language={language} style={resolvedTheme === "dark" ? loaded.dark : loaded.light} customStyle={{ margin: 0, padding: "1rem", fontSize: "13px", lineHeight: "20px" }}>{code}</SyntaxHighlighter>;
}
