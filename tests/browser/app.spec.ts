import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import type { State } from "../../frontend/src/types";
import { pointedIndex } from "../../frontend/src/wheelMath";

const origin = "http://127.0.0.1:5055";
async function adminLogin(request: APIRequestContext) {
  const bootstrap = await request.get("/api/admin/session");
  const session = await bootstrap.json();
  const login = await request.post("/api/admin/login", {
    data: { password: "browser-tests-only-password" },
    headers: { "X-CSRF-Token": session.csrf, Origin: origin },
  });
  expect(login.ok()).toBeTruthy();
  return login.json();
}
async function claimName(page: Page, name = "Amanda") {
  await page.goto("/");
  await page
    .getByLabel("First things first, who are you?")
    .selectOption({ label: name });
  await page.getByRole("button", { name: "That’s me, let’s begin" }).click();
  await page.getByRole("button", { name: `I am ${name}`, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `Welcome, ${name}` }),
  ).toBeVisible();
}
async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
}

test.beforeEach(async ({ request }) => {
  const admin = await adminLogin(request);
  const d = await (await request.get("/api/admin/dashboard")).json();
  expect(
    (
      await request.post("/api/admin/reset", {
        data: { event_id: d.event_id, confirmation: "RESET ENTIRE EVENT" },
        headers: { "X-CSRF-Token": admin.csrf, Origin: origin },
      })
    ).ok(),
  ).toBeTruthy();
});

test("desktop landing and the 360px mobile experience fit without horizontal scrolling", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Amanda se Kersfees" }),
  ).toBeVisible();
  await expect(
    page.getByLabel("First things first, who are you?"),
  ).toBeVisible();
  await noOverflow(page);
  await page
    .locator(".choose-stage")
    .evaluate((node) =>
      Promise.all(node.getAnimations().map((animation) => animation.finished)),
    );
  await page.screenshot({ path: "artifacts/desktop.png", fullPage: true });
  await page.setViewportSize({ width: 360, height: 800 });
  await noOverflow(page);
  await page.screenshot({ path: "artifacts/mobile.png", fullPage: true });
  await page.getByRole("button", { name: /A secret worth keeping/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(errors).toEqual([]);
});

test("the live animation points to the committed result and a returning browser restores it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await claimName(page);
  const initial = await (await page.request.get("/api/state")).json();
  expect(initial.segments).toHaveLength(7);
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().endsWith("/api/draw") && r.request().method() === "POST",
    ),
    page.getByRole("button", { name: "Spin my Christmas draw" }).click(),
  ]);
  const saved: State = await response.json();
  await expect(
    page.getByRole("button", { name: "A little Christmas magic…" }),
  ).toBeDisabled();
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  const transform = await page
    .getByTestId("wheel-rotor")
    .evaluate((node) => (node as SVGElement).style.transform);
  const rotation = Number(transform.match(/rotate\((.+)deg\)/)![1]);
  const index = pointedIndex(rotation, saved.draw!.segments.length);
  expect(saved.draw!.segments[index].id).toBe(saved.draw!.recipient.id);
  await page
    .getByTestId("result-card")
    .evaluate((node) =>
      Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished),
      ),
    );
  await page.screenshot({
    path: "artifacts/result-desktop.png",
    fullPage: true,
  });
  await page.reload();
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  await expect(page.getByLabel("First things first, who are you?")).toHaveCount(
    0,
  );
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
  await page.setViewportSize({ width: 360, height: 800 });
  await noOverflow(page);
  await page
    .getByTestId("result-card")
    .evaluate((node) =>
      Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished),
      ),
    );
  await page.screenshot({
    path: "artifacts/result-mobile.png",
    fullPage: true,
  });
});

test("refresh during a spin restores the original saved recipient", async ({
  page,
}) => {
  await claimName(page, "Name 2");
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/draw")),
    page.getByRole("button", { name: "Spin my Christmas draw" }).click(),
  ]);
  const saved: State = await response.json();
  await page.reload();
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  expect(
    (await (await page.request.get("/api/state")).json()).completed_count,
  ).toBe(1);
});

test("a lost response recovers the saved draw before another attempt", async ({
  page,
}) => {
  await claimName(page);
  await page.route("**/api/draw", async (route) => {
    await route.fetch();
    await route.abort("failed");
  });
  await page.getByRole("button", { name: "Spin my Christmas draw" }).click();
  await expect(page.getByTestId("recipient-name")).toBeVisible();
  const saved: State = await (await page.request.get("/api/state")).json();
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  expect(saved.completed_count).toBe(1);
});

test("reduced motion, admin replay and grant-new-draw keep the correct recipient", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await claimName(page);
  await page.getByRole("button", { name: "Spin my Christmas draw" }).click();
  await expect(page.getByTestId("recipient-name")).toBeVisible();
  const original: State = await (await page.request.get("/api/state")).json();
  const admin = await adminLogin(page.request);
  await page.request.post(
    `/api/admin/participants/${original.participant!.id}/replay`,
    {
      data: { event_id: original.event_id },
      headers: { "X-CSRF-Token": admin.csrf, Origin: origin },
    },
  );
  await expect(page.getByTestId("recipient-name")).toHaveText(
    original.draw!.recipient.name,
  );
  const adminPage = await page.context().newPage();
  await adminPage.goto("/admin");
  await adminPage
    .getByRole("button", { name: "Grant new draw for Amanda", exact: true })
    .click();
  const newDrawDialog = adminPage.getByRole("dialog");
  await expect(newDrawDialog.getByRole("textbox")).toHaveCount(0);
  await expect(
    newDrawDialog.getByRole("button", { name: "Yes, give a new draw" }),
  ).toBeEnabled();
  await adminPage.screenshot({
    path: "artifacts/new-draw-confirmation.png",
    fullPage: true,
  });
  await newDrawDialog
    .getByRole("button", { name: "Yes, give a new draw" })
    .click();
  await expect(newDrawDialog).toHaveCount(0);
  await adminPage.close();
  await expect(
    page.getByRole("button", { name: "Spin my Christmas draw" }),
  ).toBeVisible({ timeout: 12000 });
  await expect(page.getByTestId("recipient-name")).toHaveCount(0);
  await page.getByRole("button", { name: "Spin my Christmas draw" }).click();
  await expect(page.getByTestId("recipient-name")).toBeVisible();
  expect(
    (await (await page.request.get("/api/state")).json()).completed_count,
  ).toBe(1);
});

test("admin login, names, deliberate reveal and one-use browser recovery work through the interface", async ({
  page,
  browser,
}) => {
  const participantContext = await browser.newContext({
    baseURL: origin,
    reducedMotion: "reduce",
  });
  const participant = await participantContext.newPage();
  await claimName(participant);
  await participant
    .getByRole("button", { name: "Spin my Christmas draw" })
    .click();
  await expect(participant.getByTestId("recipient-name")).toBeVisible();
  const saved: State = await (
    await participant.request.get("/api/state")
  ).json();
  await page.goto("/admin");
  await page
    .getByLabel("Administrator password")
    .fill("browser-tests-only-password");
  await page.getByRole("button", { name: "Open Amanda’s corner" }).click();
  await expect(
    page.getByRole("heading", { name: "The Christmas list" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit names" })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Reveal recipients", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Reveal the saved recipients" })
    .click();
  await expect(
    page.getByText(`For ${saved.draw!.recipient.name}`, { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Hide recipients" }).click();
  await expect(
    page.getByText(`For ${saved.draw!.recipient.name}`, { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Recover browser for Amanda", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Reset browser & create recovery link" })
    .click();
  const recovery = await page
    .getByLabel("Private one-use recovery link")
    .inputValue();
  await page.getByRole("button", { name: "Done", exact: true }).click();
  await page.screenshot({
    path: "artifacts/admin-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 360, height: 800 });
  await noOverflow(page);
  await page.screenshot({ path: "artifacts/admin-mobile.png", fullPage: true });
  const recoveredContext = await browser.newContext({ baseURL: origin });
  const recovered = await recoveredContext.newPage();
  await recovered.goto(recovery);
  await recovered.getByRole("button", { name: "Reconnect my browser" }).click();
  await expect(recovered.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  await participant.reload();
  await expect(
    participant.getByText("Amanda can help you reconnect."),
  ).toBeVisible();
  await recoveredContext.close();
  await participantContext.close();
});

test("participant and admin screens have no serious accessibility violations", async ({
  page,
}) => {
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  await page.setViewportSize({ width: 360, height: 800 });
  await page.goto("/");
  await expect(
    page.getByLabel("First things first, who are you?"),
  ).toBeVisible();
  const participantAudit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    participantAudit.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
  await adminLogin(page.request);
  await page.goto("/admin");
  await expect(
    page.getByRole("heading", { name: "The Christmas list" }),
  ).toBeVisible();
  const adminAudit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    adminAudit.violations.map((v) => ({
      id: v.id,
      impact: v.impact,
      nodes: v.nodes.map((n) => ({
        target: n.target,
        summary: n.failureSummary,
      })),
    })),
  ).toEqual([]);
});

test("the final participant still gets an animated reveal with just one valid segment", async ({
  page,
  browser,
}) => {
  for (let i = 0; i < 7; i++) {
    const context = await browser.newContext({ baseURL: origin });
    const request = context.request;
    const state: State = await (await request.get("/api/state")).json();
    const bound: State = await (
      await request.post("/api/claim", {
        data: {
          event_id: state.event_id,
          participant_id: state.participants[i].id,
        },
        headers: { "X-CSRF-Token": state.csrf, Origin: origin },
      })
    ).json();
    const draw = await request.post("/api/draw", {
      data: {
        event_id: bound.event_id,
        draw_version: bound.participant!.draw_version,
      },
      headers: { "X-CSRF-Token": bound.csrf, Origin: origin },
    });
    expect(draw.ok()).toBeTruthy();
    await context.close();
  }
  await page.setViewportSize({ width: 360, height: 800 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await claimName(page, "Name 8");
  const state: State = await (await page.request.get("/api/state")).json();
  expect(state.segments).toHaveLength(1);
  await page.getByRole("button", { name: "Spin my Christmas draw" }).click();
  await expect(page.getByTestId("recipient-name")).toHaveText(
    state.segments[0].name,
  );
  expect(
    (await (await page.request.get("/api/state")).json()).completed_count,
  ).toBe(8);
  await noOverflow(page);
});

test("an admin reset during an in-flight animation cancels the stale reveal", async ({
  page,
}) => {
  await claimName(page);
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/draw")),
    page.getByRole("button", { name: "Spin my Christmas draw" }).click(),
  ]);
  const saved: State = await response.json();
  const admin = await adminLogin(page.request);
  await page.request.post(
    `/api/admin/participants/${saved.participant!.id}/new-draw`,
    {
      data: {
        event_id: saved.event_id,
        draw_version: saved.participant!.draw_version,
        confirmation: "NEW DRAW",
      },
      headers: { "X-CSRF-Token": admin.csrf, Origin: origin },
    },
  );
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByRole("button", { name: "Spin my Christmas draw" }),
  ).toBeEnabled();
  // Wait past the original animation; its stale callback must never reveal a recipient.
  await expect
    .poll(async () => {
      const current: State = await (
        await page.request.get("/api/state")
      ).json();
      return current.participant?.draw_version;
    })
    .toBe(1);
  await page.waitForTimeout(5700);
  await expect(page.getByTestId("recipient-name")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Spin my Christmas draw" }),
  ).toBeEnabled();
});

test("admin can edit the placeholders and full reset uses a simple confirmation button", async ({
  page,
  browser,
}) => {
  await adminLogin(page.request);
  await page.goto("/admin");
  await page
    .getByRole("textbox", { name: "Name 2", exact: true })
    .fill("Benedict");
  await page.getByRole("button", { name: "Save names", exact: true }).click();
  await expect(page.getByText("Benedict", { exact: true })).toBeVisible();
  const context = await browser.newContext({ baseURL: origin });
  const participant = await context.newPage();
  await claimName(participant, "Benedict");
  await page
    .getByRole("button", { name: "Reset entire event", exact: true })
    .click();
  const confirm = page
    .getByRole("dialog")
    .getByRole("button", { name: "Yes, reset everyone", exact: true });
  await expect(confirm).toBeEnabled();
  await expect(page.getByRole("dialog").getByRole("textbox")).toHaveCount(0);
  await confirm.click();
  await participant.reload();
  await expect(
    participant.getByLabel("First things first, who are you?"),
  ).toBeVisible();
  const state: State = await (
    await participant.request.get("/api/state")
  ).json();
  expect(state.participant).toBeNull();
  expect(state.participants.some((p) => p.claimed)).toBe(false);
  // Restore the fixture names for repeated test runs; the UI edit was already exercised.
  const session = await (await page.request.get("/api/admin/session")).json();
  const d = await (await page.request.get("/api/admin/dashboard")).json();
  await page.request.post("/api/admin/names", {
    data: {
      event_id: d.event_id,
      revision: d.revision,
      names: [
        "Amanda",
        "Name 2",
        "Name 3",
        "Name 4",
        "Name 5",
        "Name 6",
        "Name 7",
        "Name 8",
      ],
    },
    headers: { "X-CSRF-Token": session.csrf, Origin: origin },
  });
  await context.close();
});

test("the three-stage journey zooms into the wheel and reveals falling presents beside it", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator("main")).toHaveAttribute("data-stage", "choose");
  await expect(page.getByTestId("wheel-3d-stage")).not.toBeVisible();
  await expect(page.getByTestId("gift-stack")).toHaveCount(0);
  await claimName(page);
  await expect(page.locator("main")).toHaveAttribute("data-stage", "wheel");
  await expect(page.getByTestId("wheel-3d-stage")).toBeVisible();
  await expect(page.getByTestId("gift-stack")).toHaveCount(0);
  await page
    .locator(".wheel-3d-entrance")
    .evaluate((node) =>
      Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished),
      ),
    );
  await page.screenshot({
    path: "artifacts/wheel-3d-desktop.png",
    fullPage: true,
  });
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/api/draw")),
    page.getByRole("button", { name: "Spin my Christmas draw" }).click(),
  ]);
  const saved: State = await response.json();
  await expect(page.locator("main")).toHaveAttribute("data-stage", "reveal");
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
  await expect(page.getByTestId("gift-stack")).toBeVisible();
  await expect(page.getByTestId("celebration-bursts")).toBeAttached();
  const revealTiming = await page
    .getByTestId("result-card")
    .evaluate((node) => {
      const gifts = Array.from(node.querySelectorAll(".present-drop")).map(
        (gift) => {
          const style = getComputedStyle(gift);
          return {
            duration: parseFloat(style.animationDuration),
            end:
              parseFloat(style.animationDuration) +
              parseFloat(style.animationDelay),
          };
        },
      );
      const name = getComputedStyle(node.querySelector(".gift-name-drop")!);
      return {
        gifts,
        nameStart: parseFloat(name.animationDelay),
        nameOpacity: Number(name.opacity),
      };
    });
  expect(revealTiming.gifts.every((gift) => gift.duration >= 2.8)).toBe(true);
  expect(revealTiming.nameStart).toBeGreaterThan(
    Math.max(...revealTiming.gifts.map((gift) => gift.end)),
  );
  expect(revealTiming.nameOpacity).toBe(0);
  await expect(page.getByTestId("recipient-name")).toHaveClass(
    /recipient-name-3d/,
  );
  await page
    .getByTestId("result-card")
    .evaluate((node) =>
      Promise.all(
        node
          .getAnimations({ subtree: true })
          .map((animation) => animation.finished),
      ),
    );
  const wheel = await page.getByTestId("wheel-3d-stage").boundingBox();
  const gifts = await page.getByTestId("result-card").boundingBox();
  expect(wheel!.x + wheel!.width).toBeLessThanOrEqual(gifts!.x + 5);
  await page.screenshot({
    path: "artifacts/presents-3d-desktop.png",
    fullPage: true,
  });
  await expect
    .poll(() =>
      page
        .locator(".celebration-burst b")
        .evaluateAll((nodes) =>
          nodes.every((node) => Number(getComputedStyle(node).opacity) < 0.01),
        ),
    )
    .toBe(true);
  await page.setViewportSize({ width: 360, height: 800 });
  await noOverflow(page);
  await expect(page.getByTestId("recipient-name")).toBeInViewport();
  await page.screenshot({
    path: "artifacts/presents-3d-mobile.png",
    fullPage: true,
  });
  const { default: AxeBuilder } = await import("@axe-core/playwright");
  const audit = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(
    audit.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  ).toEqual([]);
  await page.reload();
  await expect(page.locator("main")).toHaveAttribute("data-stage", "reveal");
  await expect(page.getByTestId("recipient-name")).toHaveText(
    saved.draw!.recipient.name,
  );
});

test("Amanda can type all names and participant selectors, wheel labels and saved presents update", async ({
  page,
  browser,
}) => {
  await adminLogin(page.request);
  await page.goto("/admin");
  await expect(
    page.getByRole("heading", { name: "Names for the Christmas wheel" }),
  ).toBeVisible();
  const names = [
    "Amanda",
    "Benedict",
    "Carla",
    "Danie",
    "Elsa",
    "Freddie",
    "Gerda",
    "Hennie",
  ];
  const context = await browser.newContext({
    baseURL: origin,
    reducedMotion: "reduce",
  });
  const participant = await context.newPage();
  await participant.goto("/");
  for (let index = 0; index < 8; index++)
    await page
      .getByRole("textbox", { name: `Name ${index + 1}`, exact: true })
      .fill(names[index]);
  await page.getByRole("button", { name: "Save names", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Save names", exact: true }),
  ).toBeDisabled();
  await participant.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(participant.locator("#participant option")).toContainText(names);
  await claimName(participant);
  await expect(participant.locator(".wheel-svg text")).toHaveText(
    names.slice(1),
  );
  await participant
    .getByRole("button", { name: "Spin my Christmas draw" })
    .click();
  await expect(participant.getByTestId("recipient-name")).toBeVisible();
  const before: State = await (
    await participant.request.get("/api/state")
  ).json();
  const slot = before.participants.findIndex(
    (person) => person.id === before.draw!.recipient.id,
  );
  await page
    .getByRole("textbox", { name: `Name ${slot + 1}`, exact: true })
    .fill("Zara");
  await page.getByRole("button", { name: "Save names", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Save names", exact: true }),
  ).toBeDisabled();
  await participant.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(participant.getByTestId("recipient-name")).toHaveText("Zara");
  await expect(participant.locator(".present-name-tag")).toContainText("Zara");
  await expect(participant.locator(".wheel-svg text")).toContainText(["Zara"]);
  const after: State = await (
    await participant.request.get("/api/state")
  ).json();
  expect(after.draw!.recipient.id).toBe(before.draw!.recipient.id);
  expect(after.draw!.drawn_at).toBe(before.draw!.drawn_at);
  expect(after.draw!.segments.map((segment) => segment.id)).toEqual(
    before.draw!.segments.map((segment) => segment.id),
  );
  // Restore fixture names so repeated runs start from the same display names.
  const session = await (await page.request.get("/api/admin/session")).json();
  const dashboard = await (
    await page.request.get("/api/admin/dashboard")
  ).json();
  await page.request.post("/api/admin/names", {
    data: {
      event_id: dashboard.event_id,
      original_names: dashboard.participants.map(
        (person: { name: string }) => person.name,
      ),
      names: [
        "Amanda",
        "Name 2",
        "Name 3",
        "Name 4",
        "Name 5",
        "Name 6",
        "Name 7",
        "Name 8",
      ],
    },
    headers: { "X-CSRF-Token": session.csrf, Origin: origin },
  });
  await context.close();
});
