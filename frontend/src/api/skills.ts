import api from "./client";

export const skillsApi = {
  listSkills: async () => {
    const response = await api.get("/skills");
    return response.data;
  },
  createSkill: async (data: {
    name: string;
    description: string;
    system_prompt: string;
    allowed_tools?: string[];
    model?: string;
    max_turns?: number;
  }) => {
    const response = await api.post("/skills", data);
    return response.data;
  },
  deleteSkill: async (name: string) => {
    const response = await api.delete(`/skills/${name}`);
    return response.data;
  },
};
