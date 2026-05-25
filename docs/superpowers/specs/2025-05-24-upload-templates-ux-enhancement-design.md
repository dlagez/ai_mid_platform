# Upload Templates Page UX Enhancement

## Overview

Optimize the Upload Templates page (and the shared Construction Plan Review page) with better row interaction, smarter parse button behavior, and improved visual feedback. Both pages share the `DocumentUploadReviewPage` generic component in `frontend/src/pages/ConstructionPlanReview.tsx`.

## Changes

### 1. Clickable Rows Replace View Button

Remove the "View" button from the Actions column. Make the entire table row clickable to load parsed sections in the right panel.

- Add `onRow` to `<Table>` returning `{ onClick, style: { cursor: 'pointer' } }`
- Track `selectedFileId: number | null` state for row highlight
- Use `rowClassName` to apply a `.selected-row` CSS class with a light blue background (`token.colorPrimaryBg` from Ant Design's theme)
- Hover state: slightly darker blue tint via CSS
- PDF filename link: `onClick` calls `e.stopPropagation()` so clicking the filename opens the PDF preview modal, not the sections panel
- Parse and Delete buttons: `onClick` calls `e.stopPropagation()` to prevent row-click when interacting with action buttons

### 2. Smart Parse Button

The Parse button adapts its label, icon, and behavior based on `parse_status`:

| `parse_status` | Label | Icon | Behavior |
|---|---|---|---|
| `uploaded` | "Parse" | `ReloadOutlined` | Direct parse, no confirmation |
| `parsing` | "Parsing..." | `SyncOutlined` with `spin` | Disabled, shows spinner |
| `parsed` | "Re-parse" | `ReloadOutlined` | Confirmation modal before re-parsing |
| `failed` | "Retry" | `ReloadOutlined` | Direct retry, no confirmation |

**Confirmation modal** (only for `parsed` status):
- Title: "Re-parse this document?"
- Body: "Re-parsing will delete existing parsed sections and rebuild them."
- Buttons: "Cancel" / "Re-parse" (primary, danger-style)
- Uses Ant Design `Modal.confirm`

**Per-row loading state:** Replace the global `loading.parse` boolean with `parsingFileId: number | null` so only the active row's parse button shows a spinner. This allows users to interact with other rows while one is parsing.

### 3. Additional UX Enhancements

**a) Better empty state for the right panel:**
- New copy: "Click a document row on the left to view its parsed sections here."

**b) Actions column width reduction:**
- Reduce from 220px to ~160px (only Parse + Delete remain, View removed)

**c) Dynamic Sections card title:**
- Changes from static "Sections" to "Sections — filename.docx" when a document is selected
- Provides clear visual connection between the selected row and displayed content

**d) Guard against viewing unparsed documents:**
- When a user clicks a row where `parse_status` is `uploaded` or `parsing`, show an info message: "This document hasn't been parsed yet. Click 'Parse' to start."
- Prevents confusing empty sections result

## Files Modified

| File | Changes |
|---|---|
| `frontend/src/pages/ConstructionPlanReview.tsx` | All UI changes: row click, smart parse button, selected state, confirmation modal, empty state copy, card title |
| `frontend/src/styles.css` | Add `.selected-row` and `.clickable-row:hover` styles |

## What Does NOT Change

- Backend API — no changes needed, all data (`parse_status`, `created_at`) already available
- `documentService.ts` — existing types and functions are sufficient
- Two-column layout — kept as-is
- PDF preview modal — unchanged
- Construction Plan Review page — benefits from all changes automatically (shared component)
- Chapter Profile functionality — untouched
