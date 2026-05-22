import { apiClient } from "./apiClient";

export type ReviewTemplate = {
  id: number;
  name: string;
  code: string | null;
  work_type: string | null;
  source_document_id: number | null;
  description: string | null;
  version: string;
  status: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
};

export type ReviewTemplatePayload = {
  name?: string;
  code?: string | null;
  work_type?: string | null;
  source_document_id?: number | null;
  description?: string | null;
  version?: string;
  status?: string;
};

export type ReviewTemplateListResult = {
  items: ReviewTemplate[];
  total: number;
};

export type ImportTemplateRequest = {
  document_id: number;
  name?: string | null;
  code?: string | null;
  work_type?: string | null;
  description?: string | null;
};

export type ImportTemplateResult = {
  template_id: number;
  section_rule_count: number;
};

export type TemplateSectionRule = {
  id: number;
  template_id: number;
  parent_id: number | null;
  section_code: string | null;
  standard_title: string;
  level: number;
  order_no: number;
  required: boolean;
  aliases: string[];
  required_points: string[];
  min_word_count: number;
  risk_level: string;
  match_strategy: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  children?: TemplateSectionRule[];
};

export type TemplateSectionRuleListResult = {
  items: TemplateSectionRule[];
  flat_items: TemplateSectionRule[];
};

export type TemplateSectionRulePayload = {
  parent_id?: number | null;
  section_code?: string | null;
  standard_title?: string;
  level?: number;
  order_no?: number;
  required?: boolean;
  aliases?: string[];
  required_points?: string[];
  min_word_count?: number;
  risk_level?: string;
  match_strategy?: string;
  enabled?: boolean;
};

export const listReviewTemplates = async () => {
  const { data } = await apiClient.get<ReviewTemplateListResult>("/review-templates");
  return data;
};

export const getReviewTemplate = async (id: number) => {
  const { data } = await apiClient.get<ReviewTemplate>(`/review-templates/${id}`);
  return data;
};

export const createReviewTemplate = async (payload: ReviewTemplatePayload) => {
  const { data } = await apiClient.post<ReviewTemplate>("/review-templates", payload);
  return data;
};

export const updateReviewTemplate = async (id: number, payload: ReviewTemplatePayload) => {
  const { data } = await apiClient.patch<ReviewTemplate>(`/review-templates/${id}`, payload);
  return data;
};

export const archiveReviewTemplate = async (id: number) => {
  const { data } = await apiClient.delete<ReviewTemplate>(`/review-templates/${id}`);
  return data;
};

export const importReviewTemplateFromDocument = async (payload: ImportTemplateRequest) => {
  const { data } = await apiClient.post<ImportTemplateResult>("/review-templates/import-from-document", payload);
  return data;
};

export const activateReviewTemplate = async (id: number) => {
  const { data } = await apiClient.post<ReviewTemplate>(`/review-templates/${id}/activate`);
  return data;
};

export const disableReviewTemplate = async (id: number) => {
  const { data } = await apiClient.post<ReviewTemplate>(`/review-templates/${id}/disable`);
  return data;
};

export const listTemplateSectionRules = async (templateId: number) => {
  const { data } = await apiClient.get<TemplateSectionRuleListResult>(`/review-templates/${templateId}/section-rules`);
  return data;
};

export const createTemplateSectionRule = async (templateId: number, payload: TemplateSectionRulePayload) => {
  const { data } = await apiClient.post<TemplateSectionRule>(`/review-templates/${templateId}/section-rules`, payload);
  return data;
};

export const updateTemplateSectionRule = async (ruleId: number, payload: TemplateSectionRulePayload) => {
  const { data } = await apiClient.patch<TemplateSectionRule>(`/template-section-rules/${ruleId}`, payload);
  return data;
};

export const deleteTemplateSectionRule = async (ruleId: number) => {
  const { data } = await apiClient.delete<TemplateSectionRule>(`/template-section-rules/${ruleId}`);
  return data;
};
