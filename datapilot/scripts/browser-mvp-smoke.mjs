/** Real MVP browser flow, including immutable cleaning and localized dark UI. */
import { chromium, expect } from '@playwright/test';
import { existsSync, mkdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';

const base = process.env.DATAPILOT_BROWSER_URL || 'http://localhost:3000';
const output = process.env.DATAPILOT_SCREENSHOTS || join(tmpdir(), 'datapilot-mvp-screenshots');
mkdirSync(output, {recursive:true});
const executablePath = process.env.CHROMIUM_PATH || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox', '--disable-dev-shm-usage']});
const context = await browser.newContext({viewport:{width:1440,height:1000}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const email = `mvp-browser-${randomBytes(8).toString('hex')}@example.test`;
const password = randomBytes(24).toString('base64url');
const csv = Buffer.from('product,amount,cost,quantity,date,note\n Notebook ,120,60,2,2026-01-01,\n Notebook ,120,60,2,2026-01-01,\nPencil,90,30,1,2026-01-02,ready\n');
async function nav(name) {await page.getByRole('link',{name,exact:true}).first().click();}
async function cleanedVersion() {
  const picker = page.getByRole('combobox',{name:'Dataset version',exact:true});
  await expect(picker.locator('option').filter({hasText:'Cleaned'})).toHaveCount(1);
  const value = await picker.locator('option').filter({hasText:'Cleaned'}).getAttribute('value');
  await picker.selectOption(value);
  await expect(page.getByRole('status').filter({hasText:'Loading workbench'})).toHaveCount(0);
}
try {
  await page.goto(`${base}/sign-in`);
  await page.getByRole('button',{name:'Create account',exact:true}).click();
  await page.getByLabel('Your name').fill('MVP browser validation');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Create account',exact:true}).last().click();
  await page.waitForURL('**/app');
  await page.getByLabel('Workspace name').fill('MVP browser workspace');
  await page.getByRole('button',{name:'Create workspace',exact:true}).click();
  await expect(page.getByText('Workspace created. You can now import your sources.')).toBeVisible();
  await nav('Import sources');
  await page.getByLabel('Select multiple CSV or XLSX files',{exact:true}).setInputFiles({name:'sales.csv',mimeType:'text/csv',buffer:csv});
  await page.getByRole('button',{name:'Import 1 file',exact:true}).click();
  await expect(page.getByText('1 of 1 completed',{exact:false})).toBeVisible({timeout:100000});
  await nav('Data sources');
  await page.getByRole('link',{name:'sales.csv sales.csv',exact:true}).click();
  await expect(page.getByRole('tab',{name:'Data preview'})).toBeVisible();
  await nav('Cleaning review');
  await page.getByRole('button',{name:'Add operation',exact:true}).click();
  await page.getByRole('combobox',{name:'Cleaning operation',exact:true}).selectOption('drop_duplicates');
  await page.getByRole('button',{name:'Add operation',exact:true}).click();
  await page.getByRole('button',{name:'Preview cleaning',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Review proposed changes',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Save cleaned version',exact:true})).toBeDisabled();
  await page.screenshot({path:join(output,'cleaning-review.png'),fullPage:true});
  await page.getByLabel('I reviewed this preview and approve saving a cleaned version.',{exact:true}).check();
  await page.getByRole('button',{name:'Save cleaned version',exact:true}).click();
  await expect(page.getByText('Cleaned version saved. Your original source is preserved.',{exact:true})).toBeVisible();
  await nav('Analysis setup');
  await cleanedVersion();
  await page.getByLabel('Analysis name',{exact:true}).fill('Verified sales');
  await page.getByRole('combobox',{name:'Revenue column',exact:true}).selectOption('amount');
  await page.getByRole('combobox',{name:'Cost column',exact:true}).selectOption('cost');
  await page.getByRole('combobox',{name:'Quantity column',exact:true}).selectOption('quantity');
  await page.getByRole('combobox',{name:'Date column',exact:true}).selectOption('date');
  await page.getByRole('combobox',{name:'Category column',exact:true}).selectOption('product');
  const [analysisResponse] = await Promise.all([
    page.waitForResponse(response => response.request().method()==='POST' && response.url().endsWith('/analyses')),
    page.getByRole('button',{name:'Run analysis',exact:true}).click(),
  ]);
  const originalAnalysis = await analysisResponse.json();
  await expect(page.getByText('Analysis saved from the selected dataset version.',{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'View analysis results',exact:true}).click();
  await expect(page.getByText('210',{exact:true}).first()).toBeVisible();
  await expect(page.getByText('120',{exact:true}).first()).toBeVisible();
  await expect(page.getByRole('img',{name:'By category',exact:true})).toBeVisible();
  await page.getByLabel('Dashboard title',{exact:true}).fill('Verified dashboard');
  await page.getByRole('button',{name:'Save dashboard',exact:true}).click();
  await expect(page.getByText('Dashboard saved.',{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Open dashboards',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Verified dashboard',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading',{name:'Verified dashboard',exact:true})).toBeVisible();
  // A saved dashboard can show a different analysis from the analysis picker.
  // Saving the visible snapshot must retain its original version and metrics.
  const secondAnalysis = await page.evaluate(async ({url, original}) => {
    const response = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({
      dataset_id:original.dataset_id, version_id:original.version_id,
      name:'Filtered alternative', mapping:original.mapping, filters:{date_to:'2026-01-01'},
    })});
    if (!response.ok) throw new Error(`Alternative analysis failed: ${response.status}`);
    return response.json();
  }, {url:analysisResponse.url(), original:originalAnalysis});
  await page.reload();
  await expect(page.getByRole('heading',{name:'Verified dashboard',exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Saved analysis',exact:true}).selectOption(secondAnalysis.id);
  await page.waitForFunction(id => Object.entries(localStorage).some(([key,value]) => key.startsWith('datapilot.analysis.') && value===id), secondAnalysis.id);
  await expect(page.getByText('210',{exact:true}).first()).toBeVisible();
  await page.getByLabel('Dashboard title',{exact:true}).fill('Copied visible dashboard');
  const [copiedResponse] = await Promise.all([
    page.waitForResponse(response => response.request().method()==='POST' && response.url().endsWith('/dashboards')),
    page.getByRole('button',{name:'Save dashboard',exact:true}).click(),
  ]);
  const copiedDashboard = await copiedResponse.json();
  expect(copiedDashboard.analysis_id).toBe(originalAnalysis.id);
  expect(copiedDashboard.analysis.metrics.revenue).toBe('210');
  await page.reload();
  await expect(page.getByRole('heading',{name:'Copied visible dashboard',exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Saved analysis',exact:true}).selectOption(originalAnalysis.id);
  await page.waitForFunction(id => Object.entries(localStorage).some(([key,value]) => key.startsWith('datapilot.analysis.') && value===id), originalAnalysis.id);
  await page.getByLabel('Theme',{exact:true}).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.screenshot({path:join(output,'dashboard-dark.png'),fullPage:true});
  await nav('AI settings');
  await page.getByRole('combobox',{name:'Provider',exact:true}).selectOption('openai');
  await page.getByLabel('Model',{exact:true}).fill('gpt-4.1-mini');
  await page.locator('input[type=password]').fill('validation-only-browser-key-1234');
  await page.getByRole('button',{name:'Save AI settings',exact:true}).click();
  await expect(page.getByText('AI settings saved.',{exact:true})).toBeVisible();
  await page.reload();
  await expect(page.getByText('A key is saved: ••••1234',{exact:true})).toBeVisible();
  await page.getByLabel('Remove the saved API key',{exact:true}).check();
  await page.getByRole('button',{name:'Save AI settings',exact:true}).click();
  await expect(page.getByText('No key saved for this provider.',{exact:true})).toBeVisible();
  await page.getByRole('combobox',{name:'Provider',exact:true}).selectOption('local');
  await page.getByRole('button',{name:'Save AI settings',exact:true}).click();
  await expect(page.getByText('AI settings saved.',{exact:true})).toBeVisible();
  await nav('Ask your data');
  await cleanedVersion();
  await page.getByRole('combobox',{name:'AI skill',exact:true}).selectOption('business_analyst');
  await page.getByLabel('Your question',{exact:true}).fill('Explain the confirmed revenue and profit.');
  await page.getByRole('button',{name:'Ask with selected skill',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Evidence',exact:true})).toBeVisible();
  await expect(page.getByText(/210/).last()).toBeVisible();
  await page.screenshot({path:join(output,'skill-answer.png'),fullPage:true});
  await nav('Export & report');
  for(const format of ['CSV','XLSX','JSON','PDF','Power BI package']) {
    const button = page.getByRole('button',{name:format,exact:true}).last();
    const [download] = await Promise.all([page.waitForEvent('download'),button.click()]);
    const bytes = readFileSync(await download.path());
    if (!bytes.length) throw new Error(`Empty ${format} export`);
    if (format==='PDF' && bytes.subarray(0,5).toString()!=='%PDF-') throw new Error('Invalid PDF');
    if (['XLSX','Power BI package'].includes(format) && bytes.subarray(0,2).toString()!=='PK') throw new Error('Invalid ZIP container');
  }
  await page.getByLabel('Language',{exact:true}).selectOption('fr');
  await expect(page.locator('html')).toHaveAttribute('lang','fr');
  await expect(page.getByRole('link',{name:'Sources de données',exact:true})).toBeVisible();
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang','fr');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.getByLabel('Langue',{exact:true}).selectOption('ar');
  await expect(page.locator('html')).toHaveAttribute('lang','ar');
  await expect(page.locator('html')).toHaveAttribute('dir','rtl');
  await expect(page.getByRole('link',{name:'مصادر البيانات',exact:true})).toBeVisible();
  await page.screenshot({path:join(output,'arabic-export-dark.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+1);
  if(overflow)throw new Error('Arabic mobile MVP page overflows horizontally');
  await page.screenshot({path:join(output,'arabic-mobile.png'),fullPage:true});
  if(errors.length)throw new Error(`Browser page errors: ${errors.join('; ')}`);
  console.log('PASS: real browser cleaning approval, version selection, mapped metrics, saved dashboard/reload and visible-snapshot save, provider/model/key lifecycle, skill answer, five downloads, dark preference, French and Arabic RTL/mobile.');
  console.log(`Screenshots: ${output}`);
} catch(error) {
  await page.screenshot({path:join(output,'mvp-failure.png'),fullPage:true});
  throw error;
} finally {
  await browser.close();
}
