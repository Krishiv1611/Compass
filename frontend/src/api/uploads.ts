import api from "./client";

export const uploadsApi = {
  getCapabilities: async (sessionId: string) => {
    const response = await api.get(
      `/sessions/${sessionId}/uploads/capabilities`
    );
    return response.data;
  },
  listUploads: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}/uploads`);
    return response.data;
  },
  uploadFile: async (sessionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await api.post(`/sessions/${sessionId}/uploads`, form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },
  deleteUpload: async (sessionId: string, uploadId: string) => {
    const response = await api.delete(
      `/sessions/${sessionId}/uploads/${uploadId}`
    );
    return response.data;
  },
};
