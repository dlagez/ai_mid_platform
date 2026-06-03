import type { ReactNode } from "react";
import { Col, Empty, Row, Tree, Typography } from "antd";
import type { DataNode } from "antd/es/tree";

export type SectionTreeItem<T> = {
  id: number;
  title: string;
  content?: string | null;
  children: T[];
};

type ResponsiveCol = {
  xs?: number;
  sm?: number;
  md?: number;
  lg?: number;
  xl?: number;
  xxl?: number;
};

type SectionTreeViewerProps<T extends SectionTreeItem<T>> = {
  sections: T[];
  selectedSection: T | null;
  expandedKeys: string[];
  onExpand: (keys: string[]) => void;
  onSelectSection: (section: T | null) => void;
  emptyDescription?: ReactNode;
  selectEmptyDescription?: ReactNode;
  treeClassName?: string;
  contentClassName?: string;
  treeCol?: ResponsiveCol;
  contentCol?: ResponsiveCol;
  renderTitle?: (section: T) => ReactNode;
  renderDetail?: (section: T) => ReactNode;
};

export const SectionTreeViewer = <T extends SectionTreeItem<T>,>({
  sections,
  selectedSection,
  expandedKeys,
  onExpand,
  onSelectSection,
  emptyDescription = "No sections found.",
  selectEmptyDescription = "Select a section",
  treeClassName,
  contentClassName,
  treeCol = { xs: 24, lg: 10 },
  contentCol = { xs: 24, lg: 14 },
  renderTitle,
  renderDetail,
}: SectionTreeViewerProps<T>) => {
  if (!sections.length) {
    return <Empty description={emptyDescription} />;
  }

  const detailNode = selectedSection ? (
    renderDetail ? (
      renderDetail(selectedSection)
    ) : (
      <DefaultSectionDetail section={selectedSection} />
    )
  ) : (
    <Empty description={selectEmptyDescription} />
  );

  return (
    <Row gutter={[16, 16]}>
      <Col {...treeCol}>
        <div className={["plan-section-tree", treeClassName].filter(Boolean).join(" ")}>
          <Tree
            blockNode
            expandedKeys={expandedKeys}
            onExpand={(keys) => onExpand(keys.map(String))}
            selectedKeys={selectedSection ? [String(selectedSection.id)] : []}
            treeData={toSectionTreeData(sections, renderTitle)}
            onSelect={(keys) => {
              const key = keys[0];
              onSelectSection(key ? findSection(sections, Number(key)) : null);
            }}
          />
        </div>
      </Col>
      <Col {...contentCol}>
        <div className={["plan-section-content", contentClassName].filter(Boolean).join(" ")}>
          {detailNode}
        </div>
      </Col>
    </Row>
  );
};

const DefaultSectionDetail = <T extends SectionTreeItem<T>,>({ section }: { section: T }) => (
  <>
    <Typography.Title level={4}>{section.title}</Typography.Title>
    <Typography.Paragraph>{section.content || "No content found for this section."}</Typography.Paragraph>
  </>
);

const toSectionTreeData = <T extends SectionTreeItem<T>,>(
  sections: T[],
  renderTitle?: (section: T) => ReactNode,
): DataNode[] =>
  sections.map((section) => ({
    key: String(section.id),
    title: renderTitle ? renderTitle(section) : section.title,
    children: toSectionTreeData(section.children, renderTitle),
  }));

export const getSectionTreeKeys = <T extends SectionTreeItem<T>,>(sections: T[]): string[] =>
  sections.flatMap((section) => [String(section.id), ...getSectionTreeKeys(section.children)]);

export const findSection = <T extends SectionTreeItem<T>,>(sections: T[], id: number): T | null => {
  for (const section of sections) {
    if (section.id === id) {
      return section;
    }
    const child = findSection(section.children, id);
    if (child) {
      return child;
    }
  }
  return null;
};

export const findFirstSection = <T extends SectionTreeItem<T>,>(sections: T[]): T | null => sections[0] ?? null;
