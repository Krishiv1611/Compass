import { useEffect, useMemo, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import type { Extension } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { EditorView } from "@codemirror/view";
import { useTheme } from "@/components/ThemeProvider";

interface CodeMirrorEditorProps {
  code: string;
  onChange: (value: string) => void;
  language: string;
  readOnly?: boolean;
}

const languageCache = new Map<string, Extension>();

async function loadLanguage(language: string): Promise<Extension | null> {
  const normalized = language.toLowerCase();
  const cached = languageCache.get(normalized);
  if (cached) return cached;
  let extension: Extension | null = null;
  switch (normalized) {
    case "javascript":
    case "typescript": {
      const { javascript } = await import("@codemirror/lang-javascript");
      extension = javascript({ typescript: normalized === "typescript" });
      break;
    }
    case "python": extension = (await import("@codemirror/lang-python")).python(); break;
    case "css": extension = (await import("@codemirror/lang-css")).css(); break;
    case "html": extension = (await import("@codemirror/lang-html")).html(); break;
    case "json": extension = (await import("@codemirror/lang-json")).json(); break;
    case "markdown": extension = (await import("@codemirror/lang-markdown")).markdown(); break;
  }
  if (extension) languageCache.set(normalized, extension);
  return extension;
}

export default function CodeMirrorEditor({ code, onChange, language, readOnly = false }: CodeMirrorEditorProps) {
  const { resolvedTheme } = useTheme();
  const [languageExtension, setLanguageExtension] = useState<Extension | null>(null);

  useEffect(() => {
    let active = true;
    setLanguageExtension(null);
    void loadLanguage(language).then((extension) => { if (active) setLanguageExtension(extension); });
    return () => { active = false; };
  }, [language]);

  const extensions = useMemo(() => {
    const exts: Extension[] = [];
    if (languageExtension) exts.push(languageExtension);
    exts.push(EditorView.theme({
      "&": { backgroundColor: "var(--surface)", color: "var(--ink)" },
      ".cm-content": { caretColor: "var(--primary)" },
      ".cm-gutters": { backgroundColor: "var(--surface)", color: "var(--ink-muted)", borderColor: "var(--border)" },
      ".cm-activeLine, .cm-activeLineGutter": { backgroundColor: "color-mix(in srgb, var(--primary) 8%, transparent)" },
    }));
    return exts;
  }, [languageExtension]);

  return (
    <div className="h-full w-full overflow-hidden [&>.cm-editor]:h-full [&>.cm-editor]:w-full [&_.cm-scroller]:font-mono [&_.cm-scroller]:text-[13px] [&_.cm-scroller]:leading-[21px] [&_.cm-content]:py-4">
      <CodeMirror
        value={code}
        height="100%"
        theme={resolvedTheme === "dark" ? oneDark : "light"}
        extensions={extensions}
        onChange={onChange}
        readOnly={readOnly}
        basicSetup={{
          lineNumbers: true,
          highlightActiveLineGutter: true,
          highlightSpecialChars: true,
          history: true,
          foldGutter: true,
          drawSelection: true,
          dropCursor: true,
          allowMultipleSelections: true,
          indentOnInput: true,
          syntaxHighlighting: true,
          bracketMatching: true,
          closeBrackets: true,
          autocompletion: true,
          rectangularSelection: true,
          crosshairCursor: true,
          highlightActiveLine: true,
          highlightSelectionMatches: true,
          closeBracketsKeymap: true,
          defaultKeymap: true,
          searchKeymap: true,
          historyKeymap: true,
          foldKeymap: true,
          completionKeymap: true,
          lintKeymap: true,
        }}
      />
    </div>
  );
}
