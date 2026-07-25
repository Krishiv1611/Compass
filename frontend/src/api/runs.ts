import api from "./client";

export const runsApi = {
  getSessionRuns: async (sessionId: string) => {
    const response = await api.get(`/sessions/${sessionId}/runs`);
    return response.data;
  },
  cancelRun: async (sessionId: string, runId: string) => {
    const response = await api.post(
      `/sessions/${sessionId}/runs/${runId}/cancel`
    );
    return response.data;
  },
};
