const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({viewport:{width:390,height:844}});
  await page.goto('http://127.0.0.1:8000/#results');
  await page.waitForSelector('.page-view.active[data-view="results"]', {timeout:10000});
  const visible = await page.isVisible('#results-table-wrap');
  const box = await page.$eval('#results-table-wrap', el => {
    const r = el.getBoundingClientRect();
    return {width:r.width,height:r.height,top:r.top,left:r.left,display:getComputedStyle(el).display,visibility:getComputedStyle(el).visibility,opacity:getComputedStyle(el).opacity};
  });
  console.log('visible:', visible);
  console.log(box);
  await browser.close();
})();