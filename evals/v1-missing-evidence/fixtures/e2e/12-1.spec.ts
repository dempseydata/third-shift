import { test, expect } from "@playwright/test";
import { quill, freshHome, shoot } from "./helpers";

test('prints a header row `time,text` then one row per entry, oldest first', async ({ page }) => {
  const home = freshHome();
  quill(home, "add", "first");
  quill(home, "add", "second");
  const { stdout, code } = quill(home, "export");
  const rows = stdout.trim().split("\n");
  expect(code).toBe(0);
  expect(rows[0]).toBe("time,text");
  expect(rows.slice(1).map((r) => r.split(",").pop())).toEqual(["first", "second"]);
  await shoot(page, 'verify/evidence/12/1.png');
});
