// Execute the actual page script against a small fake DOM and HTTP responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = {};
const ids = [...html.matchAll(/id="([^"]+)"/g)].map(m => m[1]);
ids.forEach(id => elements[id] = { textContent: '' });
let fail = false;
let rfid = {status: 'ready', last_uid: '0102030404', last_read_at: '2026-10-06 00:30:00', error: null};
const context = vm.createContext({
    document: { getElementById(id) { assert.ok(elements[id], `Missing element ${id}`); return elements[id]; } },
    fetch: async () => { if (fail) throw Error('offline'); return {ok: true, json: async () => ({temp: 0, humidity: 0, light: 0, rfid})}; },
    setInterval() {}, alert() {}, console: {log() {}, error() {}}
});
(async () => {
    vm.runInContext(source, context);
    await context.updateData();
    assert.equal(elements.rfidUid.textContent, '0102030404');
    assert.equal(elements.lightCard.textContent, 0);
    assert.equal(elements.tempCard.textContent, 0);
    rfid = {status: 'init_error', last_uid: null, last_read_at: null, error: '<not html>'};
    await context.updateData();
    assert.equal(elements.rfidUid.textContent, '尚未讀卡');
    assert.equal(elements.rfidStatus.textContent, '初始化失敗');
    assert.equal(elements.rfidError.textContent, '<not html>');
    fail = true;
    await context.updateData();
    assert.equal(elements.status.textContent, '🔴 連接失敗');
    fail = false;
    await context.updateData();
    assert.equal(elements.status.textContent, '🟢 正常');
    console.log('RFID page script: PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
