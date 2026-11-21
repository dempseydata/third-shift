import { test, expect } from "@playwright/test";
import { quill, freshHome, shoot } from "./helpers";

test('is quoted as RFC 4180 requires', async ({ page }) => {
  const home = freshHome();
  quill(home, "add", 'said "hi", left');
  const { stdout } = quill(home, "export");
  expect(stdout.trim().split("\n")[1]).toMatch(/,"said ""hi"", left"$/);
  await shoot(page, 'verify/evidence/12/2.png');
});
