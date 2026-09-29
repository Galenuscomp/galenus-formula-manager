import { describe, expect, it } from "vitest";
import { passwordOk, passwordRules } from "@/lib/passwordRules";

const failed = (pw, email) => passwordRules(pw, email).filter((r) => !r.ok).map((r) => r.label);

describe("passwordRules", () => {
  it("accepts a long password with a letter and a digit", () => {
    expect(passwordOk("Fresh password 42", "tal@example.test")).toBe(true);
  });

  it("names each broken rule", () => {
    expect(failed("short1")).toEqual(["At least 10 characters"]);
    expect(failed("no digits here")).toEqual(["At least one digit"]);
    expect(failed("1234567890")).toEqual(["At least one letter"]);
    expect(failed("newuser2026x", "newuser@example.test")).toEqual(["Does not contain your e-mail address"]);
  });
});
