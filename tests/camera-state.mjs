import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const events = {}, nodes = {}, deviceEvents = {};
function element(id) {
  return nodes[id] ||= {
    value: '', disabled: false, style: {}, dataset: {},
    classList: { toggle() {}, add() {}, remove() {} },
    appendChild(option) { if (!this.value) this.value = option.value; },
    querySelectorAll() { return []; }, addEventListener() {},
    getContext() { return { clearRect() {} }; }, async play() {},
    set innerHTML(value) { this.html = value; if (id === 'camera-select') this.value = ''; },
    get innerHTML() { return this.html; },
  };
}
let currentDevice = 'second', connectedId, devices = ['first', 'second'];
const stream = { getVideoTracks: () => [{ getSettings: () => ({ deviceId: currentDevice }) }] };
const cameras = [{ id: 'registered-second', device_id: 'second', nome: 'Webcam', tipo: 'browser' }];
const context = {
  document: { getElementById: element, createElement: () => ({}), querySelector: () => element('stage') },
  navigator: { mediaDevices: { addEventListener: (name, fn) => deviceEvents[name] = fn } },
  EdgeAuth: { current: () => ({ id: 'admin' }) },
  EdgeDB: { users: [{ id: 'admin', cargo: 'administrador' }], cameras },
  CameraAPI: { supported: () => true, supportError: () => '', stop() {},
    list: async () => devices.map(deviceId => ({ deviceId, label: deviceId })),
    open: async id => { currentDevice = id; return stream; } },
  showToast: message => { context.toast = message; }, clearInterval() {},
};
context.window = { addEventListener: (name, fn) => events[name] = fn,
  EdgeAILocal: { connect: id => { connectedId = id; }, close() {} } };
vm.runInNewContext(fs.readFileSync('js/cameras.js', 'utf8'), context);
events['edge-data-ready']();
await deviceEvents.devicechange();
element('camera-select').value = 'second';
await element('start-camera').onclick();
assert.equal(element('camera-select').value, 'second');
// Refresh after a successful save must preserve controls and selection.
events['edge-data-ready']();
assert.equal(element('register-camera').disabled, false);
await deviceEvents.devicechange();
assert.equal(element('camera-select').value, 'second');
// Detection belongs to the active stream even if the dropdown changes.
element('camera-select').value = 'first';
element('start-ai').onclick();
assert.equal(connectedId, 'registered-second');
// An unregistered active stream must still be blocked.
currentDevice = 'first'; connectedId = undefined;
element('start-ai').onclick();
assert.equal(connectedId, undefined);
assert.match(context.toast, /Cadastre/);
console.log('PASS selection preservation, repeated data events, stream identity, unregistered rejection');
