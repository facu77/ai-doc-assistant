import { describe, expect, it } from "vitest";
import { VERSION } from "../src/index.js";

describe("gateway", () => {
  it("expone la versión", () => {
    expect(VERSION).toBe("0.1.0");
  });
});
