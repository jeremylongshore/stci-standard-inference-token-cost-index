const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  
  // Desktop screenshot
  const desktopPage = await context.newPage();
  await desktopPage.setViewportSize({ width: 1920, height: 1080 });
  await desktopPage.goto('https://stci-production.web.app/enterprise.html');
  await desktopPage.waitForTimeout(2000);
  await desktopPage.screenshot({ path: '/tmp/enterprise-desktop.png', fullPage: true });
  console.log('Desktop screenshot saved');
  
  // Mobile screenshot (iPhone 12 Pro)
  const mobilePage = await context.newPage();
  await mobilePage.setViewportSize({ width: 390, height: 844 });
  await mobilePage.goto('https://stci-production.web.app/enterprise.html');
  await mobilePage.waitForTimeout(2000);
  await mobilePage.screenshot({ path: '/tmp/enterprise-mobile.png', fullPage: true });
  console.log('Mobile screenshot saved');
  
  // Tablet screenshot (iPad)
  const tabletPage = await context.newPage();
  await tabletPage.setViewportSize({ width: 768, height: 1024 });
  await tabletPage.goto('https://stci-production.web.app/enterprise.html');
  await tabletPage.waitForTimeout(2000);
  await tabletPage.screenshot({ path: '/tmp/enterprise-tablet.png', fullPage: true });
  console.log('Tablet screenshot saved');
  
  await browser.close();
})();
