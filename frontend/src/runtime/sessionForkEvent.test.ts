import { describe, expect, it } from "vitest";

import { mergeSessionTimelineEvents, projectSessionFork } from "./sessionForkEvent";


describe("session fork event", () => {
  it("hydrates the durable fork event without rendering its system message", () => {
    const projection = projectSessionFork([
      { id: "user-1", role: "user", content: "hello" },
      {
        id: "fork-1",
        role: "system",
        content: "Task forked",
        created_at: "2026-08-14T00:00:00Z",
        tool_calls: {
          event: "session_forked",
          source_session_id: "source-1",
          checkpoint_id: "checkpoint-1",
        },
      },
    ]);

    expect(projection.messages.map((message) => message.id)).toEqual(["user-1"]);
    expect(projection.event).toMatchObject({
      id: "fork-1",
      type: "session_forked",
      data: {
        source_session_id: "source-1",
        checkpoint_id: "checkpoint-1",
      },
    });
  });

  it("preserves the durable event when empty run history arrives later", () => {
    const forkEvent = { id: "fork-1", type: "session_forked" };

    expect(mergeSessionTimelineEvents([forkEvent], [])).toEqual([forkEvent]);
    expect(mergeSessionTimelineEvents([forkEvent], [forkEvent])).toEqual([forkEvent]);
  });
});
