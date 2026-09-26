import {test,expect} from '../../web/node_modules/@playwright/test/index.mjs';
import {fixture,mockData} from '../../tests/browser/fixtures';
test('deep search eventually renders the complete edge without another user action',async({page})=>{
 await mockData(page,fixture());await page.goto('/');
 await expect(page.locator('[data-round-id="round-4"]')).toHaveCount(0);
 await page.getByLabel('全历史搜索',{exact:true}).fill('隐藏的深层');
 await page.locator('#search-results button').first().click();
 for(const id of ['round-1','round-2','round-4'])await expect(page.locator(`[data-round-id="${id}"]`)).toHaveCount(1);
 await expect(page.locator('[data-round-id="round-4"]')).toHaveAttribute('data-generation','3');
 await expect(page.locator('.react-flow__edge')).toHaveCount(3,{timeout:1500});
 await page.waitForTimeout(300);
 await expect(page.locator('.react-flow__edge')).toHaveCount(3);
});
