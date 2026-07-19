import { useMemo } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import { css } from "@codemirror/lang-css";
import { html } from "@codemirror/lang-html";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { oneDark } from "@codemirror/theme-one-dark";

interface CodeMirrorEditorProps {
  code: string;
  onChange: (value: string) => void;
  language: string;
  readOnly?: boolean;
}

export default function CodeMirrorEditor({ code, onChange, language, readOnly = false }: CodeMirrorEditorProps) {
  const extensions = useMemo(() => {
    const exts = [];
    switch (language.toLowerCase()) {
      case "javascript":
      case "typescript":
        exts.push(javascript({ typescript: language.toLowerCase() === "typescript" }));
        break;
      case "python":
        exts.push(python());
        break;
      case "css":
        exts.push(css());
        break;
      case "html":
        exts.push(html());
        break;
      case "json":
        exts.push(json());
        break;
      case "markdown":
        exts.push(markdown());
        break;
      default:
        // fallback
        break;
    }
    return exts;
  }, [language]);

  return (
    <div className="h-full w-full overflow-hidden [&>.cm-editor]:h-full [&>.cm-editor]:w-full [&_.cm-scroller]:font-mono [&_.cm-scroller]:text-[13px] [&_.cm-scroller]:leading-[21px] [&_.cm-content]:py-4">
      <CodeMirror
        value={code}
        height="100%"
        theme={oneDark}
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
