import { apiClient } from "./apiClient";

export const fetchPdfPreviewUrl = async (url: string, params?: Record<string, string | number | undefined>) => {
  const { data } = await apiClient.get<Blob>(url, {
    params,
    responseType: "blob",
  });
  return URL.createObjectURL(new Blob([data], { type: "application/pdf" }));
};
