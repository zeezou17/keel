/** Persisted layout widths for resizable sidebars (FP-001). */

export const DEFAULT_SIDEBAR_WIDTH = 320;
export const DEFAULT_SPAR_WIDTH = 400;
export const MIN_PANEL_WIDTH = 240;

const STORAGE_KEY = "keel:layout-widths";

export interface LayoutWidths {
  sidebar: number;
  spar: number;
}

function clampWidth(value: number, viewportWidth: number): number {
  const maxWidth = Math.floor(viewportWidth * 0.5);
  return Math.min(Math.max(value, MIN_PANEL_WIDTH), Math.max(MIN_PANEL_WIDTH, maxWidth));
}

export function loadLayoutWidths(viewportWidth = window.innerWidth): LayoutWidths {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return { sidebar: DEFAULT_SIDEBAR_WIDTH, spar: DEFAULT_SPAR_WIDTH };
    }
    const parsed = JSON.parse(raw) as Partial<LayoutWidths>;
    return {
      sidebar: clampWidth(parsed.sidebar ?? DEFAULT_SIDEBAR_WIDTH, viewportWidth),
      spar: clampWidth(parsed.spar ?? DEFAULT_SPAR_WIDTH, viewportWidth),
    };
  } catch {
    return { sidebar: DEFAULT_SIDEBAR_WIDTH, spar: DEFAULT_SPAR_WIDTH };
  }
}

export function saveLayoutWidths(widths: LayoutWidths, viewportWidth = window.innerWidth): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        sidebar: clampWidth(widths.sidebar, viewportWidth),
        spar: clampWidth(widths.spar, viewportWidth),
      }),
    );
  } catch {
    // Ignore storage errors.
  }
}

export function clampPanelWidth(value: number, viewportWidth = window.innerWidth): number {
  return clampWidth(value, viewportWidth);
}
