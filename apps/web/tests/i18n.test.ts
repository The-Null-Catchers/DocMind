import { describe, expect, it } from "vitest";
import { messages } from "../lib/i18n";
describe("localization", () => { it("keeps Arabic and English keys aligned", () => { expect(Object.keys(messages.ar).sort()).toEqual(Object.keys(messages.en).sort()); }); });
