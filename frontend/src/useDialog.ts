import { useEffect, type RefObject } from "react";
export function useDialog(
  open: boolean,
  ref: RefObject<HTMLDivElement | null>,
  close: () => void,
) {
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const first = () =>
      ref.current?.querySelector<HTMLElement>(
        'input,button,[href],select,textarea,[tabindex="0"]',
      );
    first()?.focus();
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
      }
      if (event.key !== "Tab") return;
      const items = Array.from(
        ref.current?.querySelectorAll<HTMLElement>(
          'input:not(:disabled),button:not(:disabled),[href],select:not(:disabled),textarea,[tabindex="0"]',
        ) ?? [],
      );
      const start = items[0],
        end = items[items.length - 1];
      if (!start) {
        event.preventDefault();
        return;
      }
      if (
        event.shiftKey &&
        (document.activeElement === start ||
          !ref.current?.contains(document.activeElement))
      ) {
        event.preventDefault();
        end.focus();
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault();
        start.focus();
      }
    };
    document.addEventListener("keydown", key);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [open, ref, close]);
}
