/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Map Tailwind colors to VS Code theme variables
        background: 'var(--vscode-editor-background)',
        foreground: 'var(--vscode-editor-foreground)',
        border: 'var(--vscode-panel-border)',
        primary: 'var(--vscode-button-background)',
        primaryForeground: 'var(--vscode-button-foreground)',
        secondary: 'var(--vscode-editorWidget-background)',
        accent: 'var(--vscode-focusBorder)',
      }
    },
  },
  plugins: [],
}
