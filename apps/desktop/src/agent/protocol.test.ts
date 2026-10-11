import schema from "@sasu/protocol/schema.json";
import { describe, expect, it } from "vitest";
import { CoreEvent, UI_COMMAND_TYPES } from "./protocol";

describe("protocol mirror", () => {
  it("has exactly the core events python defines", () => {
    const python = Object.keys(schema.coreEvent.discriminator.mapping).sort();
    const ours = CoreEvent.options.map((o) => o.shape.type.value).sort();
    expect(ours).toEqual(python);
  });

  it("has exactly the UI commands python accepts", () => {
    const python = Object.keys(schema.uiCommand.discriminator.mapping).sort();
    expect([...UI_COMMAND_TYPES].sort()).toEqual(python);
  });

  it("parses a tool_start with defaults", () => {
    const e = CoreEvent.parse({ type: "tool_start", id: "1", name: "apps.open" });
    expect(e).toMatchObject({ args: {}, risk: "safe" });
  });
});
