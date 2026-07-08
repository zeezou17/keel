/**
 * Drag handle for resizing adjacent workspace panels (FP-001).
 */
import { useCallback, useEffect, useRef } from "react";

interface ResizeHandleProps {
  side: "left" | "right";
  onResize: (deltaX: number) => void;
  onReset: () => void;
  ariaLabel: string;
}

export function ResizeHandle({ side, onResize, onReset, ariaLabel }: ResizeHandleProps) {
  const draggingRef = useRef(false);
  const lastXRef = useRef(0);

  const handlePointerMove = useCallback(
    (event: PointerEvent) => {
      if (!draggingRef.current) {
        return;
      }
      const deltaX = event.clientX - lastXRef.current;
      lastXRef.current = event.clientX;
      onResize(side === "left" ? deltaX : -deltaX);
    },
    [onResize, side],
  );

  const stopDragging = useCallback(() => {
    draggingRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", stopDragging);
  }, [handlePointerMove]);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    draggingRef.current = true;
    lastXRef.current = event.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", stopDragging);
  };

  useEffect(() => () => stopDragging(), [stopDragging]);

  return (
    <div
      className={`resize-handle resize-handle-${side}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={ariaLabel}
      onPointerDown={handlePointerDown}
      onDoubleClick={onReset}
      title="Drag to resize. Double-click to reset."
    />
  );
}
