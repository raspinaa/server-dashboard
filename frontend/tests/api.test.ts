import { describe, it, expect } from "vitest";
import { fields, statusLabels, roles, time } from "../src/api";
describe("inventory presentation", () => {
  it("keeps independently editable resource and network fields", () => {
    expect(fields.cpu).not.toBe(fields.ram);
    expect(fields.ip).not.toBe(fields.gateway);
    expect(fields.application).not.toBe(fields.vms);
  });
  it("provides every supported workflow and project role", () => {
    expect(Object.keys(statusLabels)).toHaveLength(4);
    expect(Object.keys(roles)).toEqual([
      "viewer",
      "operator",
      "editor",
      "manager",
    ]);
  });
  it("formats the recorded timestamp for Persian users", () => {
    expect(time("2026-10-12T10:00:00Z")).toBeTruthy();
  });
});
