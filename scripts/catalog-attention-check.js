async (page) => {
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const check = (ok, message) => {
    if (!ok) throw new Error(message);
  };
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto(
    `http://127.0.0.1:5173/?catalog-check=${Date.now()}#/buyer/products`,
  );
  await page.getByRole("button", { name: "全部 100", exact: true }).waitFor();
  const names = new Set();
  for (let i = 0; i < 9; i++) {
    for (const title of await page
      .locator(".real-product-title")
      .allTextContents())
      names.add(title);
    if (i < 8)
      await page.getByRole("button", { name: "下一页", exact: true }).click();
  }
  check(
    names.size === 100,
    "All 100 unique products are reachable through pagination",
  );
  await page.getByRole("textbox", { name: "搜索商品目录" }).fill("摄像头");
  await page.getByRole("button", { name: "摄像头 1", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelectorAll(".real-product-card").length === 1,
  );
  check(
    (await page.locator(".real-product-card").count()) === 1,
    "Search and filter",
  );
  await page.locator(".real-product-image").click();
  await page.getByRole("dialog").waitFor();
  check(
    (await page.getByRole("link", { name: "查看品牌商品来源" }).count()) === 1,
    "Product provenance",
  );
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "搜索商品目录" }).fill("");
  await page.getByRole("button", { name: "全部 100", exact: true }).click();
  const images = await page.evaluate(async () => {
    const session = await fetch("/api/auth/dev/buyer", { method: "POST" }).then(
      (r) => r.json(),
    );
    const state = await fetch("/api/state", {
      headers: { Authorization: "Bearer " + session.token },
    }).then((r) => r.json());
    return await Promise.all(
      state.products.map(
        (p) =>
          new Promise((resolve) => {
            const img = new Image();
            img.onload = () => resolve({ id: p.id, ok: img.naturalWidth > 0 });
            img.onerror = () => resolve({ id: p.id, ok: false });
            img.src = p.image;
          }),
      ),
    );
  });
  check(
    images.length === 100 && images.every((i) => i.ok),
    "All 100 local product images load",
  );
  await page.screenshot({ path: "output/playwright/catalog-1672.png" });
  await page.goto("http://127.0.0.1:5173/#/seller/home");
  await page
    .getByRole("button", { name: "审核补货方案", exact: true })
    .waitFor();
  await page.locator(".inspection-details summary").click();
  check(
    (await page.locator(".inspection-details").innerText()).includes(
      "按紧急程度排序",
    ),
    "Real workflow steps",
  );
  await page.getByRole("button", { name: "审核补货方案", exact: true }).click();
  await page.getByRole("dialog").waitFor();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "审核补货方案", exact: true })
    .first()
    .click();
  await page.getByRole("heading", { name: "人工确认", exact: true }).waitFor();
  check(
    (await page.locator(".proposal-changes").innerText()).includes(
      "计划补货数量",
    ),
    "Restock approval payload",
  );
  check(
    (await page.getByRole("dialog").getByRole("checkbox").count()) === 0,
    "No extra checkbox",
  );
  await page.getByRole("button", { name: "暂不操作", exact: true }).click();
  await page.getByRole("button", { name: "查看并处理", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "在订单管理中处理" })
    .first()
    .click();
  await page.getByRole("heading", { name: "订单管理", exact: true }).waitFor();
  check(
    (await page.locator(".orders-table tbody tr").count()) === 1,
    "Deep link filters one overdue order",
  );
  check(
    !/20\d{6}/.test(
      await page
        .locator(".orders-table tbody tr td")
        .first()
        .innerText()
        .then((t) => t.split("\n")[0]),
    ),
    "Order ID has no date",
  );
  await page.goto("http://127.0.0.1:5173/?attention-check#/seller/home");
  await page.getByRole("button", { name: "查看分析", exact: true }).waitFor();
  await page.screenshot({ path: "output/playwright/attention-1672.png" });
  const layout = [];
  for (const route of [
    "/buyer/products",
    "/seller/home",
    "/seller/products",
    "/seller/orders",
  ]) {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`http://127.0.0.1:5173/?mobile=${route}#${route}`);
    if (route === "/buyer/products") {
      await page
        .getByRole("button", { name: "全部 100", exact: true })
        .waitFor();
      await page.waitForFunction(() =>
        [...document.querySelectorAll(".real-product-image img")]
          .slice(0, 2)
          .every((i) => i.complete && i.naturalWidth > 0),
      );
    } else if (route === "/seller/home")
      await page
        .getByRole("button", { name: "查看分析", exact: true })
        .waitFor();
    else await page.locator("tbody tr").first().waitFor();
    layout.push({
      route,
      overflow: await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
    });
    await page.screenshot({
      path: `output/playwright/new-390-${route.replaceAll("/", "-")}.png`,
    });
  }
  check(
    layout.every((r) => !r.overflow),
    "No mobile document overflow",
  );
  await page.setViewportSize({ width: 1672, height: 941 });
  await page.goto("http://127.0.0.1:5173/#/seller/home");
  return {
    products: names.size,
    imagesLoaded: images.filter((i) => i.ok).length,
    layout,
    errors,
  };
}
