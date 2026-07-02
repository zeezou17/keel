# FP-005 — UI theme and color palette refresh

**Status:** Backlog  
**Priority:** Later  
**Depends on:** FP-001, FP-002, FP-003 (complete current planned features first)

## Problem

The current Keel UI uses a functional but basic color palette and visual style. After the core UX improvements (resizable sidebars, manual editing, selective drill-down) are complete, the interface would benefit from a cohesive visual refresh to improve aesthetics, accessibility, and brand identity.

## Scope (to be defined)

Areas to evaluate:

| Area | Considerations |
|------|----------------|
| **Color palette** | Primary/secondary colors, semantic colors (success, warning, error), dark mode support |
| **Typography** | Font family, sizes, weights, line heights |
| **Spacing & layout** | Consistent spacing scale, component padding/margins |
| **Component styling** | Buttons, inputs, panels, cards, tooltips |
| **Canvas theme** | Node colors by type, edge styles, selection highlights |
| **Accessibility** | WCAG contrast ratios, focus indicators, color-blind friendly palette |

## Proposed phases

### Phase 0 — Research & design (current)

- [ ] Audit current color usage across components
- [ ] Gather user feedback on visual pain points
- [ ] Create design mockups / style guide
- [ ] Define color tokens and CSS custom properties strategy

### Phase 1 — Foundation

- [ ] Implement CSS custom properties / design tokens
- [ ] Update base styles (typography, spacing)
- [ ] Refactor component styles to use tokens

### Phase 2 — Component refresh

- [ ] Update sidebar and panel styles
- [ ] Refresh canvas node and edge visuals
- [ ] Polish interactive states (hover, focus, active)

### Phase 3 — Dark mode (optional)

- [ ] Implement dark theme variant
- [ ] Add theme toggle in UI
- [ ] Persist preference in localStorage

## Acceptance criteria

Deferred until Phase 0 design work completes.

## Out of scope (v1)

- Complete redesign of layout/information architecture
- Custom theming API for end users
- White-labeling support

## Notes

This feature is intentionally backlog-only. Focus on FP-001 through FP-004 first. Revisit priority after selective drill-down and manual editing are shipped — those features will establish the component patterns that the theme refresh will style.
