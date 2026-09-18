async (page) => {
  // Run through Playwright CLI run-code. No business mutation is approved.
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const base = "http://127.0.0.1:5173";
  const verify = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto(base + "/#/");
  verify(
    (await page
      .locator('a[href="https://github.com/AOBI8001/Onda"]')
      .count()) === 1,
    "GitHub link",
  );
  for (const role of ["buyer", "seller"]) {
    await page.goto(`${base}/#/${role}/agent`);
    await page.waitForResponse(
      (r) => r.url().endsWith("/api/threads") && r.status() === 200,
    );
    await page.getByRole("button", { name: "新建对话", exact: true }).click();
    const input = page.getByRole("textbox", { name: "给 Onda 发送消息" });
    await input.fill(
      role === "buyer"
        ? "帮我取消 OD-Q7M2K9 的耳机订单。"
        : "请将 P-95CC2D4C8F 的价格修改为489元。",
    );
    await page.getByRole("button", { name: "发送消息", exact: true }).click();
    await page
      .getByRole("button", { name: "查看并确认操作" })
      .waitFor({ timeout: 90000 });
    await page.locator(".execution-details summary").last().click();
    verify(
      (await page.locator(".execution-details[open]").count()) > 0,
      "Trace details",
    );
    await page.getByRole("button", { name: "查看并确认操作" }).click();
    await page.getByRole("dialog").waitFor();
    verify(
      (await page.getByRole("dialog").getByRole("checkbox").count()) === 0,
      "No extra checkbox",
    );
    verify(
      (await page.locator(".proposal-changes").innerText()).length > 0,
      "Approval shows actual change",
    );
    await page.getByRole("button", { name: "暂不操作", exact: true }).click();
    await page.getByRole("button", { name: "拒绝操作", exact: true }).click();
    await page.waitForFunction(
      () =>
        !document.querySelector('input[aria-label="给 Onda 发送消息"]')
          .disabled,
      {},
      { timeout: 90000 },
    );
    await page
      .getByRole("button", { name: "回答有帮助", exact: true })
      .last()
      .click();
    await page.screenshot({ path: `output/playwright/live-${role}-agent.png` });
    await page.reload();
    await page.waitForResponse(
      (r) => r.url().endsWith("/api/threads") && r.status() === 200,
    );
    await page.locator(".message-row.assistant").first().waitFor();
    verify(
      (await page
        .getByRole("button", { name: "拒绝操作", exact: true })
        .count()) === 0,
      "Rejected action remains settled",
    );
  }
  await page.goto(base + "/#/buyer/account");
  await page.getByRole("heading", { name: "我的订单", exact: true }).waitFor();
  await page.getByRole("button", { name: "取消订单", exact: true }).waitFor();
  await page.getByText("OD-Q7M2K9", { exact: false }).first().waitFor();
  verify(
    (await page
      .getByRole("button", { name: "取消订单", exact: true })
      .count()) === 1,
    "Buyer rejection preserved order",
  );
  return { passed: true, errors };
}
