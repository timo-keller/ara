import { expect, test } from '@playwright/test';

const baseURL = () => process.env.ARA_E2E_URL;

async function login(context, page, identity) {
  await context.addCookies([{ name: 'e2e_identity', value: identity, url: baseURL() }]);
  await page.goto(`${baseURL()}/auth/login`);
  await page.waitForURL(`${baseURL()}/reservations`);
}

async function setSynInput(page, label, value) {
  const input = page.getByLabel(label);
  await input.fill(value);
}

async function csrfFetch(page, path, options = {}) {
  return page.evaluate(
    async ({ path, options }) => {
      const csrf = document.cookie.match(/(?:^|; )ara_csrf=([^;]+)/)?.[1];
      const response = await fetch(path, {
        ...options,
        headers: { ...options.headers, 'X-CSRF-Token': csrf },
      });
      return { status: response.status, body: await response.json() };
    },
    { path, options },
  );
}

test('authenticated discovery, future/open-ended conflicts, extension, cancellation and return', async ({
  page,
  context,
}) => {
  await login(context, page, 'alpha-user');
  await page.goto(`${baseURL()}/assets`);
  await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  await expect(page.getByText('Alpha Laptop')).toBeVisible();
  await expect(page.getByText('Bravo Laptop')).toHaveCount(0);
  await page.getByText('Alpha Laptop').first().click();
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const local = (date) =>
    new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
  await setSynInput(page, 'Start', local(tomorrow));
  await setSynInput(page, 'End (optional)', local(new Date(tomorrow.getTime() + 60 * 60 * 1000)));
  await page.getByRole('button', { name: 'Reserve', exact: true }).click();
  await expect(page.getByText('Reservation created.')).toBeVisible();
  await page.getByRole('button', { name: 'Reserve', exact: true }).click();
  await expect(page.getByText('This time conflicts with the current schedule.')).toBeVisible();
  await page.goto(`${baseURL()}/reservations`);
  await page.getByRole('button', { name: 'Cancel reservation' }).click();
  await page.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(page.getByText('Reservation cancelled')).toBeVisible();
  await page.goto(`${baseURL()}/assets`);
  await page.getByText('Alpha Laptop').first().click();
  await setSynInput(page, 'Start', local(tomorrow));
  await page.getByRole('button', { name: 'Reserve', exact: true }).click();
  await page.getByRole('button', { name: 'Confirm reservation', exact: true }).click();
  await expect(page.getByText('Reservation created.')).toBeVisible();
  await setSynInput(page, 'End (optional)', local(new Date(tomorrow.getTime() + 60 * 60 * 1000)));
  await page.getByRole('button', { name: 'Reserve', exact: true }).click();
  await expect(page.getByText('This time conflicts with the current schedule.')).toBeVisible();
  await page.goto(`${baseURL()}/reservations`);
  await page.getByRole('button', { name: 'Return asset' }).click();
  await page.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(page.getByText('Asset returned')).toBeVisible();
  await page.goto(`${baseURL()}/assets`);
  await page.getByText('Alpha Laptop').first().click();
  await setSynInput(page, 'Start', local(new Date(Date.now() + 60_000)));
  await setSynInput(page, 'End (optional)', local(new Date(Date.now() + 2 * 60 * 60 * 1000)));
  await page.getByRole('button', { name: 'Reserve', exact: true }).click();
  await page.goto(`${baseURL()}/reservations`);
  await page.getByRole('button', { name: 'Extend' }).click();
  await setSynInput(page, 'New end', local(new Date(Date.now() + 3 * 60 * 60 * 1000)));
  await page.getByRole('button', { name: 'Extend', exact: true }).last().click();
  await expect(page.getByText('Reservation extended')).toBeVisible();
});

test('My reservations is the authenticated landing page and replaces legacy Home navigation', async ({
  page,
  context,
}) => {
  await login(context, page, 'alpha-user');

  await expect(page).toHaveURL(`${baseURL()}/reservations`);
  await expect(page.getByRole('heading', { name: 'My reservations' })).toBeVisible();
  const reservationsNavigation = page.locator('syn-nav-item[href="/reservations"]');
  await expect(reservationsNavigation).toHaveAttribute('current', '');
  await expect(page.getByText('Home', { exact: true })).toHaveCount(0);

  await page.goto(`${baseURL()}/home`);
  await expect(page).toHaveURL(`${baseURL()}/reservations`);
  await expect(reservationsNavigation).toHaveAttribute('current', '');
});

test('settings menu exposes notifications and preserves compact mode', async ({
  page,
  context,
}) => {
  await login(context, page, 'alpha-user');

  const settings = page.getByRole('button', { name: 'Settings' });
  const accountName = page.locator('.account-name');
  const applicationName = page.locator('syn-header [part="content"] > [part="label"]');
  await expect(accountName).toHaveText('alpha-user');
  const [accountBox, applicationBox, settingsBox] = await Promise.all([
    accountName.boundingBox(),
    applicationName.boundingBox(),
    settings.boundingBox(),
  ]);
  expect(accountBox).not.toBeNull();
  expect(applicationBox).not.toBeNull();
  expect(settingsBox).not.toBeNull();
  expect(accountBox.x + accountBox.width).toBeLessThan(settingsBox.x);
  expect(
    Math.abs(accountBox.y + accountBox.height / 2 - (applicationBox.y + applicationBox.height / 2)),
  ).toBeLessThanOrEqual(1);
  expect(
    Math.abs(accountBox.y + accountBox.height / 2 - (settingsBox.y + settingsBox.height / 2)),
  ).toBeLessThanOrEqual(1);
  await settings.focus();
  await settings.press('Enter');
  await expect(page.getByText('Compact mode')).toBeVisible();
  await expect(page.getByText('Notifications', { exact: true })).toBeVisible();

  await page.locator('syn-switch').locator('[part="control"]').click();
  await expect(page.locator('syn-switch')).toHaveAttribute('checked', '');
  await expect(page.locator('syn-switch')).toHaveAttribute('size', 'small');
  await expect(settings).not.toHaveAttribute('size');
  await page.goto(`${baseURL()}/assets`);
  await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  await expect(page.locator('syn-input[label="Search assets"]')).toHaveAttribute('size', 'small');
  await page.reload();
  await expect(page.locator('syn-switch')).toHaveAttribute('checked', '');
  await expect(settings).not.toHaveAttribute('size');
  await expect(page.locator('syn-switch')).toHaveAttribute('size', 'small');
});

test('group admin is scoped in the UI, API, and audit history while a user is denied', async ({
  browser,
}) => {
  const adminContext = await browser.newContext();
  const admin = await adminContext.newPage();
  await login(adminContext, admin, 'alpha-admin');
  await admin.goto(`${baseURL()}/asset-administration`);
  await expect(admin.getByRole('heading', { name: 'Asset administration' })).toBeVisible();
  await expect(admin.getByText('Alpha Laptop')).toBeVisible();
  await expect(admin.getByText('Bravo Laptop')).toHaveCount(0);
  const bravoGroupId = '20000000-0000-0000-0000-000000000002';
  const denied = await csrfFetch(admin, '/api/assets', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ group_id: bravoGroupId, name: 'Forbidden asset', asset_type: 'laptop' }),
  });
  expect(denied.status).toBe(403);
  await admin.goto(`${baseURL()}/audit`);
  await expect(admin.getByText('e2e_alpha_event')).toBeVisible();
  await expect(admin.getByText('e2e_bravo_event')).toHaveCount(0);
  const scopedAudit = await csrfFetch(admin, `/api/audit-events?group_id=${bravoGroupId}`);
  expect(scopedAudit.status).toBe(200);
  expect(scopedAudit.body.items).toEqual([]);
  await adminContext.close();

  const userContext = await browser.newContext();
  const user = await userContext.newPage();
  await login(userContext, user, 'alpha-user');
  await user.goto(`${baseURL()}/asset-administration`);
  await expect(user).toHaveURL(`${baseURL()}/reservations`);
  const auditDenied = await csrfFetch(user, '/api/audit-events');
  expect(auditDenied.status).toBe(403);
  await userContext.close();
});

test('asset administration provides a keyboard-selectable responsive master-detail editor', async ({
  browser,
}) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'alpha-admin');

  const manageableAssets = await csrfFetch(page, '/api/assets?archived=false&limit=100');
  const groupId = manageableAssets.body.items[0].group_id;
  for (let index = 0; index < 20; index += 1) {
    const response = await csrfFetch(page, '/api/assets', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        group_id: groupId,
        name: `Scrollable asset ${index}`,
        asset_type: 'laptop',
      }),
    });
    expect(response.status).toBe(201);
  }
  await page.goto(`${baseURL()}/asset-administration`);

  const workspace = page.locator('.asset-workspace');
  const listPane = page.locator('.asset-list-pane');
  const editorPane = page.locator('.asset-editor');
  const asset = page.getByRole('button', { name: 'Edit Alpha Laptop' });
  expect(
    await workspace.evaluate(
      (node) => getComputedStyle(node).gridTemplateColumns.split(' ').length,
    ),
  ).toBe(2);
  await asset.focus();
  await asset.press('Enter');
  await expect(page.getByText('Editing Alpha Laptop')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Edit Alpha Laptop, selected' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await expect(page.getByRole('combobox', { name: 'Filter by asset type' })).toBeVisible();
  await expect(page.locator('syn-select[label="Filter by asset type"]')).not.toHaveAttribute(
    'help-text',
    /.+/,
  );
  await expect(listPane).toHaveCSS('overflow-y', 'auto');
  await expect(editorPane).toHaveCSS('overflow-y', 'auto');
  expect(await listPane.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(await editorPane.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);

  await listPane.evaluate((node) => (node.scrollTop = 100));
  const listScrollBeforeEditorScroll = await listPane.evaluate((node) => node.scrollTop);
  await editorPane.evaluate((node) => (node.scrollTop = node.scrollHeight));
  expect(await editorPane.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  expect(await listPane.evaluate((node) => node.scrollTop)).toBe(listScrollBeforeEditorScroll);
  const editorScrollBeforeListScroll = await editorPane.evaluate((node) => node.scrollTop);
  await listPane.evaluate((node) => (node.scrollTop = node.scrollHeight));
  expect(await listPane.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  expect(await editorPane.evaluate((node) => node.scrollTop)).toBe(editorScrollBeforeListScroll);

  await setSynInput(page, 'Filter assets by name', 'return');
  await expect(page.getByRole('button', { name: 'Edit Alpha Laptop' })).toHaveCount(0);
  await expect(page.locator('.asset-list-item[aria-current="true"]')).toHaveCount(0);
  await expect(page.getByText('Its editor draft is retained')).toBeVisible();
  await setSynInput(page, 'Filter assets by name', '');
  await expect(page.getByRole('button', { name: 'Edit Alpha Laptop, selected' })).toHaveCount(1);

  await page.getByRole('button', { name: 'Create asset', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create asset' }).last()).toBeVisible();
  await expect(page.locator('.asset-list-item[aria-current="true"]')).toHaveCount(0);

  await page.setViewportSize({ width: 640, height: 720 });
  expect(
    await workspace.evaluate(
      (node) => getComputedStyle(node).gridTemplateColumns.split(' ').length,
    ),
  ).toBe(1);
  await expect(listPane).toHaveCSS('overflow-y', 'visible');
  await expect(editorPane).toHaveCSS('overflow-y', 'visible');
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight > window.innerHeight),
  ).toBe(true);
  await expect(page.getByRole('heading', { name: 'Managed assets' })).toBeVisible();
  await expect(
    page.locator('.list-heading').getByRole('button', { name: 'Create asset', exact: true }),
  ).toBeVisible();
  await context.close();
});

test('Administration content scrolls without moving the desktop rail', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'e2e-owner');

  for (let index = 0; index < 20; index += 1) {
    const response = await csrfFetch(page, '/api/groups', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ name: `Tall administration group ${index}` }),
    });
    expect(response.status).toBe(201);
  }

  await page.goto(`${baseURL()}/administration`);
  await expect(page.getByRole('heading', { name: 'Group administration' })).toBeVisible();
  await expect(
    page.locator('.list-item strong').filter({ hasText: 'Tall administration group 19' }),
  ).toBeVisible();

  const shell = page.locator('.appshell');
  const content = page.locator('.appshell-content-inner');
  const rail = page.locator('syn-side-nav');
  const logout = page.locator('syn-side-nav > syn-nav-item[slot="footer"]');
  expect(await content.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight),
  ).toBe(true);
  const railBox = await rail.boundingBox();
  const logoutBox = await logout.boundingBox();
  expect(railBox).not.toBeNull();
  expect(logoutBox).not.toBeNull();
  expect(railBox.y + railBox.height).toBeLessThanOrEqual(720);
  expect(logoutBox.y + logoutBox.height).toBeLessThanOrEqual(720);

  await content.evaluate((node) => (node.scrollTop = node.scrollHeight));
  expect(await content.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  const railAfterScroll = await rail.boundingBox();
  expect(railAfterScroll).not.toBeNull();
  expect(railAfterScroll.y + railAfterScroll.height).toBeLessThanOrEqual(720);

  await page.setViewportSize({ width: 640, height: 720 });
  await expect(content).toHaveCSS('overflow-y', 'visible');
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight > window.innerHeight),
  ).toBe(true);
  await context.close();
});
