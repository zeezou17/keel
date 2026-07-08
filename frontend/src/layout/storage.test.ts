import { describe, expect, it } from "vitest";

import { clampPanelWidth, DEFAULT_SIDEBAR_WIDTH, DEFAULT_SPAR_WIDTH, MIN_PANEL_WIDTH } from "./storage";

describe("layout storage helpers", () => {
  it("clamps widths between minimum and half the viewport", () => {
    expect(clampPanelWidth(100, 1280)).toBe(MIN_PANEL_WIDTH);
    expect(clampPanelWidth(900, 1280)).toBe(640);
    expect(clampPanelWidth(400, 1280)).toBe(400);
  });

  it("exposes stable defaults", () => {
    expect(DEFAULT_SIDEBAR_WIDTH).toBe(320);
    expect(DEFAULT_SPAR_WIDTH).toBe(400);
  });
});
