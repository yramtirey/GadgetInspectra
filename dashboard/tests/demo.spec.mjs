import { test, expect } from '@playwright/test';
import { WebSocketServer } from 'ws';

async function step(page, count) {
  for (let index = 0; index < count; index++) await page.getByRole('button', { name: 'Next step', exact: true }).click();
}

for (const [scenario, outcome, action] of [
  ['0', 'Inspection passed', null],
  ['1', 'Rework verified', 'Approve simulated rework'],
  ['2', 'Inspection failed', 'Approve simulated rework'],
  ['1', 'Inspection failed', 'Reject inspection (no rework)'],
  ['3', 'Inspection failed', null],
]) {
  test(`scenario ${scenario}, ${action ?? 'no review'} → ${outcome}`, async ({ page }) => {
    const sockets = [], errors = [], failedAssets = [];
    page.on('websocket', socket => sockets.push(socket.url()));
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => { if (response.status() >= 400) failedAssets.push(response.url()); });
    await page.goto('./');
    await expect(page).toHaveTitle('GadgetInspectra | Simulated robotic inspection');
    await expect(page.getByRole('heading', { name: 'GadgetInspectra', exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Pause', exact: true }).click();
    await page.getByLabel('Scenario', { exact: true }).selectOption(scenario);
    await step(page, scenario === '3' ? 10 : 5);
    const state = page.locator('.state-pill');
    if (scenario === '3') {
      await expect(state).toHaveText('Waiting for scan reading');
      await expect(page.getByText('Simulated timeout: 7 / 8 seconds')).toBeVisible();
      await step(page, 1);
      await expect(page.locator('.error-reason')).toHaveText('Sensor response timed out');
    }
    if (action) {
      await expect(state).toHaveText('Operator review required');
      await step(page, 3); // Review must not auto-advance.
      await expect(state).toHaveText('Operator review required');
      await page.getByRole('button', { name: action, exact: true }).click();
      await expect(page.getByRole('button', { name: action, exact: true })).toBeDisabled();
      if (action === 'Approve simulated rework') await step(page, 3);
    }
    await expect(state).toHaveText(outcome);
    await step(page, 2); // Leave terminal results visible.
    await expect(state).toHaveText(outcome);
    if (scenario === '1' && action === 'Approve simulated rework') {
      await expect(page.getByText('P02: 8.0 mm', { exact: true })).toBeVisible();
    }
    if (scenario === '2') await expect(page.locator('.error-reason')).toHaveText('Thin spot remains after simulated rework');
    await page.getByRole('button', { name: 'Restart scenario' }).click();
    await expect(state).toHaveText('Ready for inspection');
    await expect(page.locator('.reading-chip')).toHaveCount(0);
    expect(sockets).toEqual([]);
    expect(errors).toEqual([]);
    expect(failedAssets).toEqual([]);
  });
}

test('autoplay, pause, and mobile layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.clock.install();
  await page.goto('./?mode=demo');
  await page.clock.runFor(5000);
  await expect(page.locator('.state-pill')).toHaveText('Inspection passed');
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await page.getByRole('button', { name: 'Restart scenario' }).click();
  await page.clock.runFor(10000);
  await expect(page.locator('.state-pill')).toHaveText('Ready for inspection');
  await expect(page.getByText('BROWSER SIMULATION', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test('live mode keeps ROS topics and review IDs, then returns to isolated demo', async ({ page }) => {
  // Transport stub only: this does not claim ROS integration coverage.
  const server = new WebSocketServer({ port: 9090 });
  const decisions = [];
  const status = {
    run_id: 'controller-session', inspection_id: 2, scenario_id: 'thin_spot_repaired',
    robot: 'inspection_arm_01', target: 'asset_panel_A', state: 'REVIEW_REQUIRED',
    progress_percent: 65, defect_detected: true, rework_performed: false,
    minimum_thickness_mm: 6.4, threshold_mm: 7, measurements: [],
    measurement_phase: 'initial', error_reason: null,
  };
  server.on('connection', socket => socket.on('message', raw => {
    const data = JSON.parse(raw);
    if (data.op === 'subscribe' && data.topic === '/inspection/status') {
      socket.send(JSON.stringify({ op: 'publish', topic: data.topic, msg: { data: JSON.stringify(status) } }));
    }
    if (data.op === 'publish' && data.topic === '/inspection/review_action') decisions.push(JSON.parse(data.msg.data));
  }));
  try {
    await page.goto('./?mode=live');
    await expect(page.getByText('ROS ONLINE', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Approve simulated rework', exact: true }).click();
    await expect.poll(() => decisions).toEqual([{ run_id: status.run_id, inspection_id: 2, action: 'approve_rework' }]);
    for (const socket of server.clients) socket.close();
    await expect(page.getByText('ROS OFFLINE', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Approve simulated rework', exact: true })).toBeDisabled();
    const sockets = [];
    page.on('websocket', socket => sockets.push(socket.url()));
    await page.getByRole('link', { name: 'Browser demo', exact: true }).click();
    await expect(page.getByText('BROWSER SIMULATION', { exact: true })).toBeVisible();
    expect(sockets).toEqual([]);
  } finally {
    for (const socket of server.clients) socket.terminate();
    await new Promise(resolve => server.close(resolve));
  }
});
