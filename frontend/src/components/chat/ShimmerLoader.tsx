import { cn } from "@/lib/utils";

export default function ShimmerLoader({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-shimmer h-4 rounded-md bg-[linear-gradient(to_right,var(--muted)_8%,var(--border)_18%,var(--muted)_33%)]",
        className
      )}
    />
  );
}
