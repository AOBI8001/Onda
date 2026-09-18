async (page) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const routes = ['/', '/buyer/products', '/buyer/agent', '/buyer/account', '/seller/home', '/seller/products', '/seller/orders', '/seller/tickets', '/seller/agent'];
  const report = [];
  for (const viewport of [{width:1672,height:941},{width:390,height:844}]) {
    await page.setViewportSize(viewport);
    for (const route of routes) {
      const ready=route==='/' ? Promise.resolve() : page.waitForResponse(r=>r.url().endsWith(route.endsWith('agent')?'/api/threads':'/api/state')&&r.status()===200);
      await page.goto(`http://127.0.0.1:5173/?visual=${viewport.width}-${routes.indexOf(route)}#${route}`);
      await ready;
      await page.locator('.app').waitFor();
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      await page.evaluate(() => window.scrollTo(0,0));
      await page.screenshot({path:`output/playwright/current-${viewport.width}-${route.replaceAll('/','-')}.png`});
      report.push({route,width:viewport.width,...await page.evaluate(()=>({horizontalOverflow:document.documentElement.scrollWidth>innerWidth,root:!!document.querySelector('.app')}))});
    }
  }
  await page.setViewportSize({width:1672,height:941});
  await page.goto('http://127.0.0.1:5173/#/');
  return {errors,report};
}
