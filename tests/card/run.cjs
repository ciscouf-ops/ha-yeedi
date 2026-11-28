// Map card tests: node tests/card/run.cjs (needs the playwright package and Chromium).
const path = require('path');
const { chromium } = require('playwright');
const FIXTURES = require('./fixtures.cjs');

const PAGE = 'file://' + path.join(__dirname, 'harness.html');
let failed = 0;

async function open(browser, fixture, config) {
  const page = await browser.newPage({ viewport: { width: 460, height: 900 } });
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.addInitScript(([f, c]) => { window.FIXTURE = f; window.CONFIG = c; }, [FIXTURES[fixture], config || {}]);
  await page.goto(PAGE);
  await page.waitForTimeout(150);
  return { page, errors };
}

const root = (page, sel) => page.evaluate((s) => {
  const c = document.querySelector('yeedi-map-card');
  return [...c.shadowRoot.querySelectorAll(s)].length;
}, sel);

async function test(name, fn) {
  try { await fn(); console.log('ok  ', name); } catch (e) { failed++; console.log('FAIL', name, '-', e.message); }
}
const norm = (v) => JSON.stringify(v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).sort()) : v);
function eq(a, b, what) { if (norm(a) !== norm(b)) throw new Error(`${what}: ${norm(a)} != ${norm(b)}`); }

(async () => {
  const browser = await chromium.launch();

  await test('every robot renders without error', async () => {
    for (const f of Object.keys(FIXTURES)) {
      const { page, errors } = await open(browser, f);
      eq(errors, [], `${f} errors`);
      eq(await root(page, 'ha-card'), 1, `${f} card`);
      await page.close();
    }
  });

  await test('vac max: map with 3 rooms, water levels', async () => {
    const { page } = await open(browser, 'vac_max');
    eq(await root(page, 'path.room'), 3, 'rooms');
    eq(await root(page, '.wrange'), 0, 'no slider');
    await page.close();
  });

  await test('vac max: tapping rooms numbers them, Clean sends them in order', async () => {
    const { page } = await open(browser, 'vac_max');
    for (const id of [2, 1]) {
      await page.evaluate((i) => document.querySelector('yeedi-map-card').shadowRoot.querySelector(`path.room[data-room="${i}"]`).dispatchEvent(new MouseEvent('click', { bubbles: true, composed: true })), id);
      await page.waitForTimeout(30);
    }
    eq(await root(page, 'circle.badge'), 2, 'badges');
    await page.evaluate(() => document.querySelector('yeedi-map-card').shadowRoot.querySelector('[data-act="clean"]').click());
    const calls = await page.evaluate(() => window.calls);
    const rooms = calls.find((c) => c[2] && c[2].params && c[2].params.rooms);
    eq(rooms && rooms[2].params.rooms, '2,1', 'rooms sent');
    await page.close();
  });

  await test('vac station cleaning rooms: order badges of the plan', async () => {
    const { page } = await open(browser, 'vac_station');
    eq(await root(page, 'circle.badge'), 3, 'badges');
    eq(await root(page, 'circle.badge.job'), 2, 'rooms to come');
    eq(await root(page, 'path.band'), 1, 'trace');
    await page.close();
  });

  await test('M16: water slider, tank alert, station row', async () => {
    const { page } = await open(browser, 'm16');
    eq(await root(page, '.wrange'), 1, 'slider');
    eq(await root(page, '.tanks > *'), 1, 'one tank alert');
    eq(await root(page, '[data-station]'), 3, 'station buttons');
    await page.evaluate(() => {
      const r = document.querySelector('yeedi-map-card').shadowRoot.querySelector('.wrange');
      r.value = 37;
      r.dispatchEvent(new Event('change', { bubbles: true, composed: true }));
    });
    const calls = await page.evaluate(() => window.calls);
    eq(calls.at(-1), ['number', 'set_value', { entity_id: 'number.robot_water', value: 37 }], 'water call');
    await page.close();
  });

  await test('M16: history only when asked', async () => {
    let { page } = await open(browser, 'm16');
    eq(await root(page, '.hist'), 0, 'hidden by default');
    await page.close();
    ({ page } = await open(browser, 'm16', { show: { history: true } }));
    eq(await root(page, '.hrow'), 1, 'one cleaning');
    await page.close();
  });

  await test('hybrid: no outlines, rooms as buttons', async () => {
    const { page } = await open(browser, 'hybrid');
    eq(await root(page, 'path.room'), 0, 'no room shapes');
    eq(await root(page, 'button.chip'), 3, 'room buttons');
    await page.close();
  });

  await test('show: parts can be hidden', async () => {
    const { page } = await open(browser, 'vac_max', { show: { map: false, name: false, suction: false } });
    eq(await root(page, 'svg.plan'), 0, 'no map');
    eq(await root(page, '.title'), 0, 'no name');
    eq(await root(page, '.nomap button.chip'), 3, 'rooms as buttons');
    await page.close();
  });

  await test('editor writes only the changed parts', async () => {
    const { page } = await open(browser, 'vac_max');
    const got = await page.evaluate(() => {
      const ed = document.createElement('yeedi-map-card-editor');
      let out = null;
      ed.addEventListener('config-changed', (e) => { out = e.detail.config; });
      ed.setConfig({ entity: 'vacuum.robot', controls: false });
      ed.hass = window.hass;
      const d = ed.querySelector('ha-form').data;
      ed._changed({ ...d, show: { ...d.show, buttons: true, trace: false, history: true } });
      return out;
    });
    eq(got.show, { zone: false, suction: false, water: false, station: false, footer: false, trace: false, history: true }, 'show');
    eq('controls' in got, false, 'controls replaced');
    await page.close();
  });

  await browser.close();
  if (failed) { console.log(`${failed} failed`); process.exit(1); }
  console.log('all passed');
})();
