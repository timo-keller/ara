import { expect, test } from '@playwright/test';

const baseURL = () => process.env.ARA_E2E_URL;

async function login(context, page, identity) {
  await context.addCookies([{ name: 'e2e_identity', value: identity, url: baseURL() }]);
  await page.goto(`${baseURL()}/auth/login`);
  await page.waitForURL(`${baseURL()}/`);
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
  await expect(user).toHaveURL(`${baseURL()}/`);
  const auditDenied = await csrfFetch(user, '/api/audit-events');
  expect(auditDenied.status).toBe(403);
  await userContext.close();
});
