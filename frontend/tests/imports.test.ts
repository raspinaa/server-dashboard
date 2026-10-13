import { describe, expect, it } from "vitest";
import { defaultImportDecision } from "../src/imports";

describe("simple import defaults", () => {
  const fresh = { errors: [], current: null, candidates: [], match: null };
  it("includes valid new rows without per-row choices", () => {
    expect(defaultImportDecision(fresh, "add_only").action).toBe("apply");
    expect(defaultImportDecision(fresh, "add_only").credential).toBe(
      "preserve",
    );
  });
  it("does not silently match by a server name or import an invalid row", () => {
    expect(
      defaultImportDecision(
        { ...fresh, candidates: [{ id: "existing" }] },
        "add_update",
      ).action,
    ).toBe("skip");
    expect(
      defaultImportDecision({ ...fresh, errors: ["invalid IP"] }, "add_only")
        .action,
    ).toBe("skip");
  });
  it("only updates stable UUID matches in update mode and preserves extra disks", () => {
    const existing = { ...fresh, current: { id: "stable" }, match: "stable" };
    expect(defaultImportDecision(existing, "add_only").action).toBe("skip");
    expect(defaultImportDecision(existing, "add_update")).toMatchObject({
      action: "apply",
      match: "stable",
      disks: "merge",
    });
  });
});
