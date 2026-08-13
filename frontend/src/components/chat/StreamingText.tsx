export default function StreamingText({ content }: { content: string }) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
      {content}
      <span className="ml-1 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" />
    </div>
  );
}
