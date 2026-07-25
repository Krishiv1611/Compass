import { useEffect, useRef, useState, type ReactNode } from "react";
import type { MobileDestination } from "@/contexts/WorkbenchContext";

interface WorkbenchCompositionProps {
  centerPanel: ReactNode;
  rightPanel: ReactNode;
  showRightPanel: boolean;
  mobileDestination?: MobileDestination;
}

export default function WorkbenchComposition({
  centerPanel,
  rightPanel,
  showRightPanel,
  mobileDestination = "agent",
}: WorkbenchCompositionProps) {
  const [rightWidth, setRightWidth] = useState(380);
  const dragging = useRef(false);

  useEffect(() => {
    const move = (event: PointerEvent) => {
      if (!dragging.current) return;
      setRightWidth(Math.min(720, Math.max(320, window.innerWidth - event.clientX)));
    };
    const stop = () => { dragging.current = false; };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
    };
  }, []);

  const showMobileAgent = mobileDestination === "agent" || mobileDestination === "activity";

  return (
    <div className="flex h-full min-h-0 w-full min-w-0 overflow-hidden">
      <section className={`${showMobileAgent ? "hidden" : "flex"} min-w-0 flex-1 flex-col lg:flex`}>
        {centerPanel}
      </section>
      {showRightPanel && (
        <>
          <button
            type="button"
            aria-label="Resize agent panel"
            className="hidden w-1 shrink-0 cursor-col-resize border-l border-border hover:bg-primary/20 lg:block"
            onPointerDown={(event) => {
              event.currentTarget.setPointerCapture(event.pointerId);
              dragging.current = true;
            }}
          />
          <aside
            className={`${showMobileAgent ? "flex" : "hidden"} min-w-0 flex-1 flex-col bg-background lg:flex lg:flex-none`}
            style={{ width: `min(${rightWidth}px, 48vw)` }}
          >
            {rightPanel}
          </aside>
        </>
      )}
    </div>
  );
}
