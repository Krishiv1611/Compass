import { CheckCircle2, Circle } from "lucide-react";

type PlanChecklistProps = {
  plan: string;
  completedSteps?: number[];
};

function extractSteps(plan: string): string[] {
  const lines = plan
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const numbered = lines
    .map((line) => line.replace(/^\d+[\).]\s*/, "").trim())
    .filter((line) => line && !/^skill:/i.test(line));

  return numbered.length > 0 ? numbered : [plan.trim()];
}

export default function PlanChecklist({
  plan,
  completedSteps = [],
}: PlanChecklistProps) {
  const steps = extractSteps(plan);
  const completed = new Set(completedSteps);

  return (
    <div className="mb-2 rounded-lg border border-primary/20 bg-primary/8 p-3">
      <div className="mb-2 text-[11px] font-semibold uppercase text-muted-foreground">
        Plan
      </div>
      <ol className="space-y-2">
        {steps.map((step, index) => {
          const done = completed.has(index) || completed.has(index + 1);
          return (
            <li
              key={`${index}-${step}`}
              className={`flex gap-2 text-xs leading-5 ${
                done ? "text-muted-foreground opacity-50 line-through" : "text-foreground"
              }`}
            >
              {done ? (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
              ) : (
                <Circle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}
              <span>
                <span className="mr-1 font-mono text-[10px] text-muted-foreground">
                  {index + 1}.
                </span>
                {step}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
