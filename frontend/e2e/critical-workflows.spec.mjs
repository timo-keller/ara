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

async function expectCompactRouteGap(page, content) {
  const introduction = page.locator('.route-introduction');
  const [introductionBox, contentBox] = await Promise.all([
    introduction.boundingBox(),
    content.boundingBox(),
  ]);
  expect(introductionBox).not.toBeNull();
  expect(contentBox).not.toBeNull();
  const gap = contentBox.y - (introductionBox.y + introductionBox.height);
  expect(gap).toBeGreaterThanOrEqual(8);
  expect(gap).toBeLessThanOrEqual(12);
}

test('authenticated discovery, future/open-ended conflicts, extension, cancellation and return', async ({
  page,
  context,
}) => {
  await login(context, page, 'alpha-user');
  await page.goto(`${baseURL()}/assets`);
  await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  await expect(page.getByText('Alpha Laptop')).toBeVisible();
  const catalogue = page.getByRole('table');
  await expect(catalogue.getByRole('cell', { name: 'Available now' })).toBeVisible();
  await expect(catalogue.getByRole('cell', { name: 'Reserved by E2E Holder' })).toBeVisible();
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
  await expect(page.getByRole('link', { name: 'Alpha Laptop', exact: true })).toBeVisible();
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

test('asset catalogue exposes responsive table results and keyboard detail navigation', async ({
  browser,
}) => {
  const context = await browser.newContext({ viewport: { width: 480, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'alpha-user');
  await page.goto(`${baseURL()}/assets`);

  const table = page.getByRole('table');
  await expect(table).toBeVisible();
  expect(await table.getByRole('columnheader').allTextContents()).toEqual([
    'Asset name',
    'Asset type',
    'Description',
    'Availability',
    'Details',
  ]);
  await expect(table.getByRole('link', { name: 'Alpha Laptop', exact: true })).toBeVisible();
  await expect(table.getByText('Reserved by E2E Holder', { exact: true })).toBeVisible();
  const details = table.getByRole('link', { name: 'View details for Alpha Laptop' });
  await expect(details).toBeVisible();
  expect(await table.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
  await details.focus();
  await details.press('Enter');
  await expect(page).toHaveURL(/\/assets\/[^/]+$/);
  await context.close();
});

test('My reservations exposes keyboard lifecycle filtering, history restoration, and a responsive table', async ({
  browser,
}) => {
  const context = await browser.newContext({ viewport: { width: 480, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'alpha-user');
  await page.goto(`${baseURL()}/reservations`);

  const filters = page.getByRole('form', { name: 'Filter reservations' });
  await expect(filters).toBeVisible();
  await expect(filters.getByLabel('Asset name')).toBeVisible();
  await expect(filters.getByLabel('Asset type')).toBeVisible();
  await expect(filters.getByLabel('From')).toBeVisible();
  await expect(filters.getByLabel('To')).toBeVisible();
  const lifecycle = filters.getByRole('combobox', { name: 'Lifecycle' });
  await expect(lifecycle).toBeVisible();

  await lifecycle.focus();
  await lifecycle.press('ArrowDown');
  await lifecycle.press('Enter');
  await lifecycle.press('ArrowDown');
  await lifecycle.press('Enter');
  await lifecycle.press('Escape');
  await expect(lifecycle).toBeFocused();
  await expect(page).toHaveURL(/lifecycle=current.*lifecycle=future/);
  await expect(filters.locator('syn-tag').filter({ hasText: 'Current' })).toBeVisible();
  await expect(filters.locator('syn-tag').filter({ hasText: 'Future' })).toBeVisible();
  await expect(filters.getByRole('button', { name: 'Remove' })).toHaveCount(2);

  await filters.getByRole('button', { name: 'Clear entry' }).click();
  await expect(filters.getByRole('button', { name: 'Remove' })).toHaveCount(0);
  await page.goBack();
  await expect(filters.locator('syn-tag').filter({ hasText: 'Current' })).toBeVisible();
  await expect(filters.locator('syn-tag').filter({ hasText: 'Future' })).toBeVisible();
  await page.goForward();
  await expect(filters.getByRole('button', { name: 'Remove' })).toHaveCount(0);
  expect(await filters.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);

  const table = page.getByRole('table');
  await expect(table).toBeVisible();
  expect(await table.getByRole('columnheader').allTextContents()).toEqual([
    'Asset name',
    'Type',
    'Reservation timespan',
    'Actions and details',
  ]);
  await expect(table.getByRole('link', { name: 'Alpha Return Laptop', exact: true })).toBeVisible();
  await expect(
    table.getByRole('link', { name: 'View details for Alpha Return Laptop' }),
  ).toBeVisible();
  await expect(table.getByText('until returned')).toBeVisible();
  const currentRow = table.getByRole('row', { name: /Alpha Return Laptop/ });
  await expect(currentRow.getByRole('button', { name: 'Return asset' })).toBeVisible();
  await expect(currentRow.getByText(/\d{2}:\d{2}/)).toBeVisible();
  const expiredRow = table.getByRole('row', { name: /Alpha Expired Laptop/ });
  const expiredLifecycle = expiredRow.locator('syn-badge');
  await expect(expiredLifecycle).toHaveText(/^Expired/);
  await expiredRow.getByRole('button', { name: 'Return asset' }).click();
  await page.getByRole('button', { name: 'Confirm', exact: true }).click();
  await expect(expiredLifecycle).toHaveText(/^Returned/);
  await expect(expiredRow.getByRole('button', { name: 'Return asset' })).toHaveCount(0);
  expect(await table.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
  await context.close();
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

test('authenticated route introductions use the compact heading-to-content rhythm', async ({
  browser,
}) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'e2e-owner');

  await page.goto(`${baseURL()}/audit`);
  await expect(page.getByRole('heading', { name: 'Audit history' })).toBeVisible();
  await expectCompactRouteGap(page, page.locator('.filters'));

  await page.goto(`${baseURL()}/asset-administration`);
  await expect(page.getByRole('heading', { name: 'Asset administration' })).toBeVisible();
  await expectCompactRouteGap(page, page.locator('.asset-workspace'));

  await page.goto(`${baseURL()}/assets`);
  await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  await expectCompactRouteGap(page, page.locator('.filters'));

  await page.goto(`${baseURL()}/administration`);
  await expect(page.getByRole('heading', { name: 'Group administration' })).toBeVisible();
  await expectCompactRouteGap(page, page.locator('.group-workspace'));
  await context.close();
});

test('settings menu exposes notifications and preserves compact mode', async ({
  page,
  context,
}) => {
  await login(context, page, 'alpha-user');

  const settings = page.getByRole('button', { name: 'Settings' });
  await expect(page.locator('.account-name')).toHaveCount(0);
  await settings.focus();
  await settings.press('Enter');
  await expect(page.locator('.settings-account-name')).toHaveText('alpha-user');
  await expect(page.getByText('Compact mode')).toBeVisible();
  await expect(page.getByText('Notifications', { exact: true })).toBeVisible();
  const settingsMenu = page.locator('app-settings syn-dropdown [part="panel"]');
  await expect(settingsMenu).toBeVisible();
  expect(await settingsMenu.evaluate((node) => getComputedStyle(node).backgroundColor)).toMatch(
    /^rgb\(\d+, \d+, \d+\)$/,
  );

  await page.locator('syn-switch').locator('[part="control"]').click();
  await expect(page.locator('syn-switch')).toHaveAttribute('checked', '');
  await expect(page.locator('syn-switch')).toHaveAttribute('size', 'small');
  await expect(settings).not.toHaveAttribute('size');
  await expect(settingsMenu).toBeVisible();
  expect(await settingsMenu.evaluate((node) => getComputedStyle(node).backgroundColor)).toMatch(
    /^rgb\(\d+, \d+, \d+\)$/,
  );
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

test('Administration content scrolls within its fixed desktop surface without moving the rail', async ({
  browser,
}) => {
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
    const mapping = await csrfFetch(page, '/api/role-mappings', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        group_id: response.body.id,
        expression: 'true',
        role: 'user',
        priority: index,
        enabled: true,
      }),
    });
    expect(mapping.status).toBe(201);
    if (index === 19) {
      for (let mappingIndex = 0; mappingIndex < 10; mappingIndex += 1) {
        const extraMapping = await csrfFetch(page, '/api/role-mappings', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            group_id: response.body.id,
            expression: `contains(groups, 'scrollable-${mappingIndex}')`,
            role: 'user',
            priority: index + mappingIndex + 1,
            enabled: true,
          }),
        });
        expect(extraMapping.status).toBe(201);
      }
    }
  }

  await page.goto(`${baseURL()}/administration`);
  await expect(page.getByRole('heading', { name: 'Group administration' })).toBeVisible();
  await expect(
    page.locator('.group-list-item strong').filter({ hasText: 'Tall administration group 19' }),
  ).toBeVisible();

  const workspace = page.locator('.group-workspace');
  const groupList = page.locator('.group-list-pane');
  const groupEditor = page.locator('.group-editor');
  expect(
    await workspace.evaluate(
      (node) => getComputedStyle(node).gridTemplateColumns.split(' ').length,
    ),
  ).toBe(2);
  await expect(groupList).toHaveCSS('overflow-y', 'auto');
  await expect(groupEditor).toHaveCSS('overflow-y', 'auto');
  expect(await groupList.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  const selectedGroup = page.getByRole('button', {
    name: 'Edit Tall administration group 19',
    exact: true,
  });
  await selectedGroup.focus();
  await selectedGroup.press('Enter');
  await expect(page.getByText('Editing Tall administration group 19')).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'Edit Tall administration group 19, selected', exact: true }),
  ).toHaveAttribute('aria-current', 'true');
  expect(await groupEditor.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  await page.getByRole('button', { name: 'Create group', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create group' }).last()).toBeVisible();
  await expect(page.locator('.group-list-item[aria-current="true"]')).toHaveCount(0);

  await selectedGroup.focus();
  await selectedGroup.press('Enter');

  const shell = page.locator('.appshell');
  const content = page.locator('.appshell-content-inner');
  const main = page.locator('.appshell-main');
  const administrationContent = page.locator('.administration-content');
  const rail = page.locator('syn-side-nav');
  const logout = page.locator('syn-side-nav > syn-nav-item[slot="footer"]');
  await expect(main).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(content).toHaveCSS('overflow-y', 'hidden');
  await expect(administrationContent).toHaveCSS('overflow-y', 'hidden');
  expect(await main.evaluate((node) => node.scrollHeight <= node.clientHeight)).toBe(true);
  expect(
    await administrationContent.evaluate((node) => node.scrollHeight <= node.clientHeight),
  ).toBe(true);
  const paneBounds = await page.evaluate(() => {
    const mainBox = document.querySelector('.appshell-main').getBoundingClientRect();
    const workspaceBox = document.querySelector('.group-workspace').getBoundingClientRect();
    const editorBox = document.querySelector('.group-editor').getBoundingClientRect();
    const mainPaddingBottom = Number.parseFloat(
      getComputedStyle(document.querySelector('.appshell-main')).paddingBottom,
    );
    return {
      editorBottom: editorBox.bottom,
      workspaceBottom: workspaceBox.bottom,
      expectedBottom: mainBox.bottom - mainPaddingBottom,
    };
  });
  expect(paneBounds.editorBottom).toBeCloseTo(paneBounds.workspaceBottom, 1);
  expect(paneBounds.workspaceBottom).toBeCloseTo(paneBounds.expectedBottom, 1);
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight),
  ).toBe(true);
  const railBox = await rail.boundingBox();
  const logoutBox = await logout.boundingBox();
  expect(railBox).not.toBeNull();
  expect(logoutBox).not.toBeNull();
  expect(railBox.y + railBox.height).toBeLessThanOrEqual(720);
  expect(logoutBox.y + logoutBox.height).toBeLessThanOrEqual(720);

  const mainBeforeScroll = await main.boundingBox();
  await groupList.evaluate((node) => (node.scrollTop = node.scrollHeight));
  const listScrollBeforeEditorScroll = await groupList.evaluate((node) => node.scrollTop);
  await groupEditor.evaluate((node) => (node.scrollTop = node.scrollHeight));
  expect(await groupEditor.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  expect(await groupList.evaluate((node) => node.scrollTop)).toBe(listScrollBeforeEditorScroll);
  expect(await main.boundingBox()).toEqual(mainBeforeScroll);
  const railAfterScroll = await rail.boundingBox();
  expect(railAfterScroll).not.toBeNull();
  expect(railAfterScroll.y + railAfterScroll.height).toBeLessThanOrEqual(720);

  await page.setViewportSize({ width: 640, height: 720 });
  await expect(administrationContent).toHaveCSS('overflow-y', 'visible');
  expect(
    await workspace.evaluate(
      (node) => getComputedStyle(node).gridTemplateColumns.split(' ').length,
    ),
  ).toBe(1);
  await expect(groupList).toHaveCSS('overflow-y', 'visible');
  await expect(groupEditor).toHaveCSS('overflow-y', 'visible');
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight > window.innerHeight),
  ).toBe(true);
  await context.close();
});

test('group role mappings follow the keyboard-selected group context', async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'e2e-owner');
  const first = await csrfFetch(page, '/api/groups', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: 'Scoped mappings Alpha' }),
  });
  const second = await csrfFetch(page, '/api/groups', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: 'Scoped mappings Bravo' }),
  });
  for (const [groupId, expression] of [
    [first.body.id, "contains(groups, 'scoped-alpha')"],
    [second.body.id, "contains(groups, 'scoped-bravo')"],
  ]) {
    const mapping = await csrfFetch(page, '/api/role-mappings', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        group_id: groupId,
        expression,
        role: 'user',
        priority: 0,
        enabled: true,
      }),
    });
    expect(mapping.status).toBe(201);
  }
  await page.goto(`${baseURL()}/administration`);
  const alpha = page.getByRole('button', { name: 'Edit Scoped mappings Alpha', exact: true });
  await alpha.focus();
  await alpha.press('Enter');
  await expect(
    page.getByRole('heading', { name: 'Role mappings for Scoped mappings Alpha' }),
  ).toBeVisible();
  await expect(page.locator('.mapping-list')).toContainText('scoped-alpha');
  await expect(page.locator('.mapping-list')).not.toContainText('scoped-bravo');
  await setSynInput(page, 'JMESPath expression', 'draft retained');
  await page.getByRole('button', { name: 'Create group', exact: true }).click();
  await expect(
    page.getByText('Save and select a group before managing its role mappings.'),
  ).toBeVisible();
  await expect(page.getByLabel('JMESPath expression')).toHaveCount(0);
  const bravo = page.getByRole('button', { name: 'Edit Scoped mappings Bravo', exact: true });
  await bravo.focus();
  await bravo.press('Enter');
  await expect(page.locator('.mapping-list')).toContainText('scoped-bravo');
  await expect(page.locator('.mapping-list')).not.toContainText('scoped-alpha');
  await alpha.focus();
  await alpha.press('Enter');
  await expect(page.getByLabel('JMESPath expression')).toHaveValue('draft retained');
  await context.close();
});

test('Audit history keeps its desktop surface fixed while event cards scroll', async ({
  browser,
}) => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  await login(context, page, 'e2e-owner');

  for (let index = 0; index < 30; index += 1) {
    const response = await csrfFetch(page, '/api/groups', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ name: `Scrollable audit group ${index}` }),
    });
    expect(response.status).toBe(201);
  }

  await page.goto(`${baseURL()}/audit`);
  await expect(page.getByRole('heading', { name: 'Audit history' })).toBeVisible();
  const shell = page.locator('.appshell');
  const main = page.locator('.appshell-main');
  const content = page.locator('.appshell-content-inner');
  const events = page.locator('.audit-results .events');
  const rail = page.locator('syn-side-nav');
  await expect(events.locator('syn-card').first()).toBeVisible();
  const firstEventCard = events.locator('syn-card').first();
  const firstEventTitle = firstEventCard.locator('> h2[slot="header"]');
  await expect(firstEventTitle).toBeVisible();
  expect(await firstEventTitle.evaluate((node) => getComputedStyle(node).marginBlockStart)).toBe(
    '0px',
  );
  expect(await firstEventTitle.evaluate((node) => getComputedStyle(node).marginBlockEnd)).toBe(
    '0px',
  );
  expect(
    await firstEventCard.evaluate((node) => {
      const header = node.shadowRoot?.querySelector('[part="header"]');
      return header && getComputedStyle(header).paddingBlock;
    }),
  ).toBe('12px');
  const changeDetails = firstEventCard.locator('syn-details');
  await changeDetails.locator('[part="header"]').click();
  await expect(changeDetails).toHaveAttribute('open', '');
  await expect(main).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await expect(content).toHaveCSS('overflow-y', 'hidden');
  await expect(events).toHaveCSS('overflow-y', 'auto');
  expect(await events.evaluate((node) => node.scrollHeight > node.clientHeight)).toBe(true);
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight),
  ).toBe(true);

  await page.getByRole('button', { name: 'Settings' }).click();
  await page.locator('syn-switch').locator('[part="control"]').click();
  await expect(page.locator('syn-switch')).toHaveAttribute('checked', '');
  await expect(firstEventTitle).toBeVisible();

  const mainBeforeScroll = await main.boundingBox();
  const railBeforeScroll = await rail.boundingBox();
  await events.evaluate((node) => (node.scrollTop = node.scrollHeight));
  expect(await events.evaluate((node) => node.scrollTop)).toBeGreaterThan(0);
  expect(await main.boundingBox()).toEqual(mainBeforeScroll);
  expect(await rail.boundingBox()).toEqual(railBeforeScroll);
  await expect(page.locator('syn-pagination[aria-label="Audit history pages"]')).toBeVisible();

  await page.setViewportSize({ width: 640, height: 720 });
  await expect(events).toHaveCSS('overflow-y', 'visible');
  expect(await firstEventCard.evaluate((node) => node.scrollWidth <= node.clientWidth)).toBe(true);
  await expect(firstEventTitle).toBeVisible();
  expect(
    await shell.evaluate(() => document.documentElement.scrollHeight > window.innerHeight),
  ).toBe(true);
  await page.locator('syn-pagination[aria-label="Audit history pages"]').scrollIntoViewIfNeeded();
  await expect(page.locator('syn-pagination[aria-label="Audit history pages"]')).toBeVisible();

  await page.goto(`${baseURL()}/administration`);
  const administrationCardTitle = page.locator('.group-editor > h2[slot="header"]');
  await expect(administrationCardTitle).toBeVisible();
  expect(
    await administrationCardTitle.evaluate((node) =>
      Number.parseFloat(getComputedStyle(node).marginBlockStart),
    ),
  ).toBeGreaterThan(0);
  await context.close();
});
