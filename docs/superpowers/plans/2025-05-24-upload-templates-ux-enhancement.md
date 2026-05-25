# Upload Templates Page UX Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the Upload Templates (and Construction Plan Review) page with clickable rows, a smart parse button, and enhanced visual feedback.

**Architecture:** Modify the shared `DocumentUploadReviewPage` component in a single TSX file plus add CSS for row highlighting. No backend or service-layer changes needed — all required data already exists on `DocumentRecord`.

**Tech Stack:** React 18, TypeScript, Ant Design 5, react-router-dom

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `frontend/src/pages/ConstructionPlanReview.tsx` | Modify | All component logic: row click, smart parse button, state, modal, empty state |
| `frontend/src/styles.css` | Modify | Row highlight and hover styles |

---

### Task 1: Add CSS for clickable and selected rows

**Files:**
- Modify: `frontend/src/styles.css` (append after `.table-link-button` block, around line 142)

- [ ] **Step 1: Add row highlight styles**

Add the following CSS after the `.table-link-button` block (after line 142):

```css
.document-row {
  cursor: pointer;
  transition: background-color 0.15s ease;
}

.document-row:hover {
  background-color: #e6f4ff;
}

.document-row-selected {
  background-color: #e6f4ff;
}

.document-row-selected:hover {
  background-color: #bae0ff;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style: add clickable and selected row styles for document table"
```

---

### Task 2: Update imports and add `selectedFileId` state

**Files:**
- Modify: `frontend/src/pages/ConstructionPlanReview.tsx`

- [ ] **Step 1: Add `SyncOutlined` to the icon imports**

On line 24, add `SyncOutlined` to the existing icon import:

```tsx
import {
  CloudUploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  ProfileOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
```

- [ ] **Step 2: Add `Modal` to the antd imports**

Add `Modal` to the existing antd import (line 3–18):

```tsx
import {
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Modal,
  Popconfirm,
  Row,
  Space,
  Table,
  Tag,
  Tree,
  Typography,
  Upload,
  message,
} from "antd";
```

- [ ] **Step 3: Add `selectedFileId` state and `parsingFileId` state**

After the existing `loading` state declaration (line 64), add two new state variables:

```tsx
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [parsingFileId, setParsingFileId] = useState<number | null>(null);
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ConstructionPlanReview.tsx
git commit -m "feat: add imports and state for selectedFileId and parsingFileId"
```

---

### Task 3: Remove View button, make rows clickable, add stopPropagation

**Files:**
- Modify: `frontend/src/pages/ConstructionPlanReview.tsx`

- [ ] **Step 1: Remove the View button from the Actions column**

Delete the View button block (lines 289–296):

```tsx
                      <Button
                        size="small"
                        icon={<FileTextOutlined />}
                        loading={loading.parse}
                        onClick={() => void handleView(record.id)}
                      >
                        View
                      </Button>
```

- [ ] **Step 2: Add `stopPropagation` to the PDF filename link**

Replace the PDF link Button's `onClick` (line 259) to add `stopPropagation`. The full render function for the File Name column becomes:

```tsx
                {
                  title: "File Name",
                  dataIndex: "file_name",
                  ellipsis: true,
                  render: (value: string, record) =>
                    isPdf(value) ? (
                      <Button
                        type="link"
                        size="small"
                        className="table-link-button"
                        onClick={(e) => {
                          e.stopPropagation();
                          void handlePreviewPdf(record);
                        }}
                      >
                        {value}
                      </Button>
                    ) : (
                      value
                    ),
                },
```

- [ ] **Step 3: Add `stopPropagation` to the Parse button and reduce action column width**

Replace the Parse button with a `stopPropagation` wrapper and update the column width. The Actions column definition becomes:

```tsx
                {
                  title: "",
                  width: enableChapterProfiles ? 300 : 160,
                  render: (_, record) => (
                    <Space size={6} wrap onClick={(e) => e.stopPropagation()}>
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={parsingFileId === record.id}
                        disabled={record.parse_status === "parsing"}
                        onClick={() => void handleParse(record)}
                      >
                        Parse
                      </Button>
                      {enableChapterProfiles ? (
                        <>
                          <Button
                            size="small"
                            icon={<ProfileOutlined />}
                            loading={loading.profile}
                            disabled={record.parse_status !== "parsed"}
                            onClick={() => void handleCreateProfileJob(record)}
                          >
                            Profile
                          </Button>
                          {profileJobs[record.id] ? (
                            <Button
                              size="small"
                              type="link"
                              className="table-link-button"
                              onClick={() => navigate(`/construction-plan/profile-jobs/${profileJobs[record.id].id}`)}
                            >
                              <Space size={4}>
                                <ProfileStatusTag status={profileJobs[record.id].status} />
                                <span>
                                  {profileJobs[record.id].processed_sections}/{profileJobs[record.id].total_sections}
                                </span>
                              </Space>
                            </Button>
                          ) : null}
                        </>
                      ) : null}
                      <Popconfirm
                        title="Delete this document?"
                        description="The uploaded file and parsed sections will be removed."
                        okText="Delete"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => void handleDelete(record)}
                      >
                        <Button size="small" danger icon={<DeleteOutlined />} loading={loading.delete}>
                          Delete
                        </Button>
                      </Popconfirm>
                    </Space>
                  ),
                },
```

- [ ] **Step 4: Add `onRow` and `rowClassName` to the Table component**

Add these two props to the `<Table<DocumentRecord>>` element (after `dataSource={files}` and before `columns`):

```tsx
              onRow={(record) => ({
                onClick: () => void handleRowClick(record),
                className: `document-row${selectedFileId === record.id ? " document-row-selected" : ""}`,
              })}
```

- [ ] **Step 5: Add the `handleRowClick` handler**

Add this handler function after `handlePreviewPdf` (around line 191):

```tsx
  const handleRowClick = async (record: DocumentRecord) => {
    setSelectedFileId(record.id);
    if (record.parse_status === "uploaded" || record.parse_status === "parsing") {
      message.info("This document hasn't been parsed yet. Click 'Parse' to start.");
      return;
    }
    if (record.parse_status === "failed") {
      message.warning("Parsing failed for this document. Click 'Retry' to try again.");
      return;
    }
    await handleView(record.id);
  };
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ConstructionPlanReview.tsx
git commit -m "feat: replace View button with clickable rows and row highlight"
```

---

### Task 4: Smart parse button with confirmation modal

**Files:**
- Modify: `frontend/src/pages/ConstructionPlanReview.tsx`

- [ ] **Step 1: Rewrite `handleParse` to accept full record and show confirmation for re-parse**

Replace the existing `handleParse` function (lines 152–164) with:

```tsx
  const handleParse = async (record: DocumentRecord) => {
    if (record.parse_status === "parsed") {
      Modal.confirm({
        title: "Re-parse this document?",
        content: "Re-parsing will delete existing parsed sections and rebuild them.",
        okText: "Re-parse",
        okType: "danger",
        cancelText: "Cancel",
        onOk: async () => {
          await executeParse(record);
        },
      });
      return;
    }
    await executeParse(record);
  };

  const executeParse = async (record: DocumentRecord) => {
    setParsingFileId(record.id);
    try {
      const result = await parseDocument(record.id);
      setParsed(result);
      selectFirstSection(result);
      setSelectedFileId(record.id);
      await refreshFiles();
    } catch {
      message.error("Parse failed.");
    } finally {
      setParsingFileId(null);
    }
  };
```

- [ ] **Step 2: Update the Parse button in the Actions column to use smart labels**

Replace the Parse button inside the `<Space>` (from Task 3, Step 3) with the smart version:

```tsx
                      <Button
                        size="small"
                        icon={
                          record.parse_status === "parsing" ? (
                            <SyncOutlined spin />
                          ) : (
                            <ReloadOutlined />
                          )
                        }
                        loading={parsingFileId === record.id}
                        disabled={record.parse_status === "parsing"}
                        onClick={() => void handleParse(record)}
                      >
                        {record.parse_status === "parsing"
                          ? "Parsing..."
                          : record.parse_status === "parsed"
                            ? "Re-parse"
                            : record.parse_status === "failed"
                              ? "Retry"
                              : "Parse"}
                      </Button>
```

- [ ] **Step 3: Remove `FileTextOutlined` from icon imports (no longer used)**

Remove `FileTextOutlined` from the import statement on line 24. The import becomes:

```tsx
import {
  CloudUploadOutlined,
  DeleteOutlined,
  ProfileOutlined,
  ReloadOutlined,
  SyncOutlined,
} from "@ant-design/icons";
```

- [ ] **Step 4: Remove `loading.parse` from the loading state**

Remove `parse` from the loading state object. Change:

```tsx
  const [loading, setLoading] = useState({ files: false, upload: false, parse: false, delete: false, profile: false });
```

to:

```tsx
  const [loading, setLoading] = useState({ files: false, upload: false, delete: false, profile: false });
```

Then remove `setLoading((s) => ({ ...s, parse: true }))` and `setLoading((s) => ({ ...s, parse: false }))` from `handleView` (lines 140, 148). The updated `handleView` becomes:

```tsx
  const handleView = async (id: number) => {
    try {
      const result = await getDocumentSections(id);
      setParsed(result);
      selectFirstSection(result);
    } catch {
      message.error("Failed to load sections.");
    }
  };
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ConstructionPlanReview.tsx
git commit -m "feat: smart parse button with status-aware labels and re-parse confirmation"
```

---

### Task 5: Update empty state, dynamic card title, final cleanup

**Files:**
- Modify: `frontend/src/pages/ConstructionPlanReview.tsx`

- [ ] **Step 1: Update the empty state text for the right panel**

Replace the `emptyDescription` prop in `TemplateUploadPage` (line 419):

```tsx
    emptyDescription="Click a document row on the left to view its parsed sections here."
```

Replace the `emptyDescription` prop in `ConstructionPlanReviewPage` (line 428):

```tsx
    emptyDescription="Click a document row on the left to view its parsed sections here."
```

- [ ] **Step 2: Make the Sections card title dynamic**

Replace the static `<Card title="Sections">` (line 353) with a dynamic title:

```tsx
          <Card title={parsed ? `Sections — ${parsed.file_name}` : "Sections"}>
```

- [ ] **Step 3: Verify the application builds without errors**

Run: `cd frontend && npm run build`
Expected: Build completes with no errors.

- [ ] **Step 4: Final commit**

```bash
git add frontend/src/pages/ConstructionPlanReview.tsx
git commit -m "feat: dynamic sections card title and improved empty state copy"
```

---

## Verification Checklist

After all tasks are complete, manually verify:

1. **Row click**: Clicking any table row highlights it (blue background) and loads sections in the right panel
2. **Row hover**: Hovering over rows shows a light blue background
3. **No View button**: The View button is gone from all rows
4. **PDF link**: Clicking a PDF filename opens the PDF preview modal (not the sections panel)
5. **Parse button labels**: Shows "Parse" for uploaded, "Parsing..." (disabled) for parsing, "Re-parse" for parsed, "Retry" for failed
6. **Re-parse confirmation**: Clicking "Re-parse" on a parsed doc shows a confirmation modal
7. **Direct parse**: Clicking "Parse" on an uploaded doc parses immediately (no confirmation)
8. **Direct retry**: Clicking "Retry" on a failed doc retries immediately (no confirmation)
9. **Per-row loading**: Only the active row's parse button shows a spinner
10. **Unparsed row click**: Clicking an uploaded/parsing row shows an info message instead of loading empty sections
11. **Dynamic card title**: Right panel title changes to "Sections — filename.ext" when a doc is selected
12. **Empty state**: Right panel shows "Click a document row on the left..." when no doc is selected
13. **Delete button**: Still works with Popconfirm, doesn't trigger row click
14. **Construction Plan page**: All changes work identically on the Construction Plan Review page
