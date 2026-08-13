import type { RunEvent } from "@/types/run";
import type { ResumePayload } from "@/types/protocol";

export interface FakeRunScenario { events: RunEvent[]; resume: ResumePayload | null }

export class FakeRunServer {
  readonly resumes: ResumePayload[] = [];
  private readonly scenarios: Record<string, FakeRunScenario>;
  constructor(scenarios: Record<string, FakeRunScenario>) { this.scenarios = scenarios; }
  replay(name: string): RunEvent[] { return this.scenarios[name].events; }
  expectedResume(name: string): ResumePayload | null { return this.scenarios[name].resume; }
  resume(payload: ResumePayload) { this.resumes.push(payload); }
}
