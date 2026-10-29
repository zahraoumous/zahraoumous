/** Real browser flow: sign-up, workspace, folder import, result, persistent session, mobile. */
import { chromium, expect } from '@playwright/test';
import { existsSync, mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';

const base = process.env.DATAPILOT_BROWSER_URL || 'http://localhost:3000';
const output = process.env.DATAPILOT_SCREENSHOTS || join(tmpdir(), 'datapilot-browser-screenshots');
mkdirSync(output, {recursive:true});
const executablePath = process.env.CHROMIUM_PATH || (existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined);
const browser = await chromium.launch({executablePath, headless:true, args:['--no-sandbox', '--disable-dev-shm-usage']});
const context = await browser.newContext({viewport:{width:1440,height:1000}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const temporary = mkdtempSync(join(tmpdir(), 'datapilot-browser-'));
const folder = join(temporary, 'Sources');
mkdirSync(join(folder,'nested'),{recursive:true});
writeFileSync(join(folder,'north.csv'),'product,amount,note\nNotebook,120,\nNotebook,120,\nPencil,90,ready\n');
writeFileSync(join(folder,'nested','south.csv'),'region,amount\nSouth,75\n');
writeFileSync(join(folder,'notes.txt'),'Unsupported file must be visibly excluded.');
const email = `browser-${randomBytes(8).toString('hex')}@example.test`;
const password = randomBytes(24).toString('base64url');
try {
  await page.goto(`${base}/sign-in`);
  await expect(page.getByRole('button',{name:'Sign in',exact:true}).last()).toBeVisible();
  await page.screenshot({path:join(output,'sign-in.png'),fullPage:true});
  await page.getByRole('button',{name:'Create account',exact:true}).click();
  await page.getByLabel('Your name').fill('Workflow validation');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Create account',exact:true}).last().click();
  await page.waitForURL('**/app',{timeout:20000});
  await page.getByLabel('Workspace name').fill('Folder processing validation');
  await page.getByRole('button',{name:'Create workspace',exact:true}).click();
  await expect(page.getByText('Workspace created. You can now import your sources.')).toBeVisible({timeout:15000});
  await page.getByRole('link',{name:'Import sources',exact:true}).first().click();
  await page.getByLabel('Select a datasource folder',{exact:true}).setInputFiles(folder);
  await expect(page.getByText('1 file was not added')).toBeVisible();
  await expect(page.getByText('Sources/nested/south.csv',{exact:true})).toBeVisible();
  await page.getByLabel('Import name').fill('Folder execution');
  await page.screenshot({path:join(output,'folder-manifest.png'),fullPage:true});
  await page.getByRole('button',{name:'Import 2 files',exact:true}).click();
  await expect(page.getByText('2 of 2 completed',{exact:false})).toBeVisible({timeout:100000});
  await page.getByRole('link',{name:'Executions',exact:true}).first().click();
  await expect(page.getByText('2 of 2 completed',{exact:false})).toBeVisible();
  await page.screenshot({path:join(output,'executions.png'),fullPage:true});
  await page.getByRole('link',{name:'View data',exact:true}).first().click();
  await expect(page.getByRole('tab',{name:'Data preview'})).toBeVisible({timeout:15000});
  await expect(page.getByText('Original source preserved',{exact:true})).toBeVisible();
  await page.getByRole('tab',{name:'Column schema'}).click();
  await expect(page.getByRole('columnheader',{name:'Completeness',exact:true})).toBeVisible();
  await page.getByRole('tab',{name:'Data preview'}).click();
  await page.reload();
  await expect(page.getByRole('tab',{name:'Data preview'})).toBeVisible({timeout:15000});
  await page.screenshot({path:join(output,'dataset-preview.png'),fullPage:true});
  const cookies = await context.cookies();
  const session = cookies.find(cookie => cookie.name === 'dp_session');
  if (!session?.httpOnly || session.sameSite !== 'Strict') throw new Error('Unsafe session cookie');
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('link',{name:'Overview',exact:true}).click();
  await expect(page.getByText('Welcome to Folder processing validation.')).toBeVisible({timeout:15000});
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  if (overflow) {
    console.error(await page.evaluate(() => ({width:window.innerWidth, scroll:document.documentElement.scrollWidth,
      elements:[...document.querySelectorAll('.workspace-shell,.sidebar,.workspace-body,.workspace-main,.content-panel,.table-scroll,.source-table,.topbar,.page-heading,.metric-strip')].map(el=>({class:el.className,width:el.getBoundingClientRect().width,scroll:el.scrollWidth,overflow:getComputedStyle(el).overflowX})),
      wide:[...document.querySelectorAll('body *')].filter(el=>el.getBoundingClientRect().right>window.innerWidth+1 && !el.closest('.table-scroll') && !el.closest('nav')).slice(0,25).map(el=>({tag:el.tagName,class:el.className,left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,position:getComputedStyle(el).position,overflow:getComputedStyle(el).overflowX}))
    })));
    await page.screenshot({path:join(output,'mobile-failure.png'),fullPage:true});
    throw new Error('Mobile page overflows horizontally');
  }
  await page.screenshot({path:join(output,'mobile-workspace.png'),fullPage:true});
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await page.waitForURL('**/sign-in');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in',exact:true}).last().click();
  await page.waitForURL('**/app');
  await expect(page.getByText('Welcome to Folder processing validation.')).toBeVisible({timeout:15000});
  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  console.log('PASS: browser sign-up, persistent workspace, folder paths, excluded files, real processing, preview/schema, reload, secure session cookie, mobile layout and sign-out/sign-in.');
  console.log(`Screenshots: ${output}`);
} finally {
  await browser.close();
  rmSync(temporary,{recursive:true,force:true});
}
