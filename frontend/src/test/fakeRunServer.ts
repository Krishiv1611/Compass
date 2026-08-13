import type { RunEvent } from "@/types/run";
import type { ResumePayload } from "@/types/protocol";

export interface FakeRunScenario { events: RunEvent[]; resume: ResumePayload | null }

export class FakeRunServer {
  readonly resumes: ResumePayload[] = [];
  constructor(private readonly scenarios: Record<string, FakeRunScenario>) {}
  replay(name: string): RunEvent[] { return this.scenarios[name].events; }
  expectedResume(name: string): ResumePayload | null { return this.scenarios[name].resume; }
  resume(payload: ResumePayload) { this.resumes.push(payload); }
}
