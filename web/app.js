const $ = (id) => document.getElementById(id);
const modes = [
  ['embers', 'Jack-o’-lantern embers', 'Warm, uneven flicker'],
  ['cauldron', 'Cauldron', 'Rolling bubbles'],
  ['ghost', 'Passing ghost', 'A drifting light'],
  ['chase', 'Chase', 'A moving tail'],
  ['breathing', 'Slow breathing', 'A gentle color pulse'],
  ['solid', 'Steady', 'No motion'],
];
const defaultGradient = [[0,255,65,0,50],[100,125,15,240,50]];
let settings = { mode: 'embers', brightness: .15, speed: 1, color: [255, 65, 0], color_mode:'solid', gradient:defaultGradient, blackout: false };
let selectedStop = 0;
let stopDrag = null, lastStopDrag = null;
let colorDraft = null, colorTimer = null, colorBusy = false, colorVersion = 0, colorJob = 0;
let lastColorCommit = null;
let port = null, reader = null, writer = null, connected = false;
let nextId = 1, pending = new Map(), disconnecting = false;
let commandQueue = Promise.resolve();
let pendingChanges = 0, stateRevision = 0;
let transport = 'usb', wifiTimer = null;
let usbBusy = false;
const WIFI_TIMEOUT_MS = 15000;
let wifiEnabled = false, wifiBusy = false, wifiFailures = 0, wifiGeneration = 0, wifiAbort = null;
const boardWebsite = new URLSearchParams(location.search).has('wifi') || !['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
document.body.classList.toggle('wifi-page', boardWebsite);
for (const [key, title, description] of modes) {
  const button = document.createElement('button');
  button.className = 'pattern'; button.dataset.mode = key; button.disabled = true;
  const label = document.createElement('span'); label.textContent = title;
  const small = document.createElement('small'); small.textContent = description;
  button.append(label, small); button.setAttribute('aria-pressed', 'false');
  button.addEventListener('click', () => change({ mode: key, blackout: false }));
  $('patterns').append(button);
}
function notice(text, error = false) { $('notice').textContent = text; $('notice').classList.toggle('error', error); }
function renderConnection() {
  $('connect').disabled = wifiBusy || usbBusy;
  $('connect').textContent = wifiBusy ? 'Connecting…' : connected ? (transport === 'wifi' ? 'Disconnect Wi-Fi' : 'Disconnect USB') : (boardWebsite ? 'Connect lights' : 'Connect USB');
  $('connection-dock').hidden = !boardWebsite || (connected && !wifiFailures);
  $('dock-status').textContent = wifiBusy ? 'Connecting to the lights…' : connected ? 'Wi-Fi delayed; retrying…' : wifiEnabled ? 'Connection lost. Reconnecting automatically…' : 'Lights disconnected';
  $('reconnect').textContent = wifiEnabled ? 'Reconnect now' : 'Connect lights';
}
function sync() {
  const enabled = connected;
  for (const control of document.querySelectorAll('.pattern, .controls input, .controls button, .palette input, .palette select, .palette button')) control.disabled = !enabled;
  for (const b of document.querySelectorAll('.pattern')) b.setAttribute('aria-pressed', String(b.dataset.mode === settings.mode));
  $('brightness').value = settings.brightness * 100;
  $('brightness-value').textContent = `${Math.round(settings.brightness * 100)}%`;
  $('speed').value = settings.speed; $('speed-value').textContent = `${settings.speed.toFixed(2)}×`;
  renderPalette();
  $('automatic').checked = settings.automatic !== false;
  $('blackout').textContent = settings.blackout ? 'Restore lights' : 'Blackout';
  $('blackout').setAttribute('aria-pressed', String(settings.blackout));
  renderConnection();
  $('save').disabled = !connected;
}
async function request(command, values, persist=true) {
  const id = nextId++;
  if (transport === 'wifi') {
    const generation = wifiGeneration;
    let response;
    try {
      response = await fetch('/api/command', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, command, settings:values, persist}), signal:AbortSignal.timeout(WIFI_TIMEOUT_MS)});
    } catch (error) {
      if (generation === wifiGeneration && wifiEnabled) recoverWifi();
      throw new Error('No confirmation from the board. Reconnecting to read its current settings; the command will not be resent.');
    }
    if (generation !== wifiGeneration) throw new Error('Connection changed. Reconnect to read the board’s current settings.');
    if (!response.ok) throw new Error(`The board returned HTTP ${response.status}.`);
    const result = await response.json();
    if (!result.ok) throw new Error(result.error);
    return result;
  }
  const response = new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('No response. Select the Feather control port and check that the firmware is running.')); }, 4000);
    pending.set(id, { resolve, reject, timer });
  });
  try { await writer.write(new TextEncoder().encode(JSON.stringify({id, command, settings: values, persist}) + '\n')); }
  catch (error) { const entry = pending.get(id); if (entry) { clearTimeout(entry.timer); pending.delete(id); entry.reject(error); } }
  return response;
}
function change(values, {persist=true, quiet=false}={}) {
  if (!connected) return Promise.resolve(false);
  const generation = wifiGeneration;
  pendingChanges++;
  commandQueue = commandQueue.then(async () => {
    if (!connected || generation !== wifiGeneration) return false;
    const update = typeof values === 'function' ? values() : values;
    const result = await request('set', update, persist);
    if (!connected || generation !== wifiGeneration) return false;
    stateRevision++;
    settings = result.settings; sync();
    renderSchedule(result.schedule, result.effective_brightness);
    const saved = ['mode','color','color_mode','gradient'].some(key => key in update);
    if (!quiet) notice(settings.blackout ? 'Blackout active. The board remains connected.' : saved && persist ? 'Pattern and color saved on the board.' : 'Settings applied to the board.');
    return true;
  }).catch(error => { sync(); notice(error.message, true); return false; }).finally(() => { pendingChanges--; });
  return commandQueue;
}
function gradientStops() { return settings.gradient || defaultGradient; }
function hex(rgb) { return '#' + rgb.map(v => v.toString(16).padStart(2,'0')).join(''); }
function drawGradient(stops) {
  const colors = [];
  stops.forEach((stop, index) => {
    colors.push(`${hex(stop.slice(1,4))} ${stop[0]}%`);
    const next = stops[index+1];
    if (next) {
      const middle = stop.slice(1,4).map((v,c) => Math.round((v + next[c+1])/2));
      colors.push(`${hex(middle)} ${stop[0] + (next[0]-stop[0])*stop[4]/100}%`);
    }
  });
  $('gradient-bar').style.background = `linear-gradient(90deg, ${colors.join(',')})`;
}
function renderPalette() {
  if ((stopDrag || pendingChanges > 1) && connected) return;
  if (!connected) stopDrag = null;
  const gradient = settings.color_mode === 'gradient';
  $('color-mode').value = gradient ? 'gradient' : 'solid';
  $('gradient-editor').hidden = !gradient;
  $('gradient-note').textContent = settings.mode === 'breathing'
    ? 'Slow breathing cycles all LEDs together through these colors and back. Stop positions and fade midpoints shape the color changes over time.'
    : 'Across both sticks, from LED 1 to LED 16. Select a stop to edit its color, position and fade.';
  const stops = gradientStops().map(stop=>[...stop]);
  if (colorDraft?.source === 'gradient' && stops[colorDraft.index]) stops[colorDraft.index].splice(1,3,...colorDraft.rgb);
  selectedStop = Math.min(selectedStop, stops.length-1);
  const stop = stops[selectedStop];
  $('color-label').textContent = gradient ? `Stop ${selectedStop+1} color` : 'Light color';
  const colorValue=hex(!gradient && colorDraft?.source === 'solid' ? colorDraft.rgb : gradient ? stop.slice(1,4) : settings.color);
  if ($('color').value !== colorValue) $('color').value=colorValue;
  if ($('gradient-stops').children.length !== stops.length) {
    const focused = document.activeElement?.dataset.stop;
    $('gradient-stops').replaceChildren();
    stops.forEach((value,index) => {
      const button = document.createElement('button');
      button.type = 'button'; button.dataset.stop = index;
      button.textContent = index+1;
      button.addEventListener('click', event => {
        if (event.detail && lastStopDrag?.index === index && performance.now()-lastStopDrag.time < 300) return;
        selectedStop=index; renderPalette(); button.focus({preventScroll:true});
      });
      button.addEventListener('pointerdown', event => startStopDrag(event,index));
      button.addEventListener('pointermove', moveStopDrag);
      button.addEventListener('pointerup', event => finishStopDrag(event,false));
      button.addEventListener('pointercancel', event => finishStopDrag(event,true));
      button.addEventListener('lostpointercapture', event => finishStopDrag(event,true));
      button.addEventListener('keydown', event => {
        if (event.key === 'Escape' && stopDrag) { finishStopDrag(null,true); return; }
        if (index === 0 || index === gradientStops().length-1 || !connected) return;
        const direction = {ArrowLeft:-1,ArrowDown:-1,ArrowRight:1,ArrowUp:1}[event.key];
        if (!direction && event.key !== 'Home' && event.key !== 'End') return;
        event.preventDefault(); selectedStop=index;
        moveStop(index,(position,low,high) => event.key === 'Home' ? low : event.key === 'End' ? high : position+direction*(event.shiftKey?10:1));
      });
      $('gradient-stops').append(button);
    });
    if (focused !== undefined) $('gradient-stops').children[Number(focused)]?.focus({preventScroll:true});
  }
  stops.forEach((value,index) => {
    const button = $('gradient-stops').children[index];
    const endpoint = index === 0 || index === stops.length-1;
    button.disabled = !connected;
    button.style.left = `${value[0]}%`; button.style.borderBottomColor = hex(value.slice(1,4));
    button.dataset.selected = String(index === selectedStop); button.dataset.endpoint = String(endpoint);
    button.setAttribute('aria-describedby','gradient-stop-help');
    button.setAttribute('role',endpoint?'button':'slider');
    button.setAttribute('aria-label', `Color stop ${index+1}${endpoint ? ` at ${value[0]}%, fixed endpoint` : ''}`);
    if (endpoint) {
      button.setAttribute('aria-pressed',String(index === selectedStop));
      for (const name of ['aria-valuemin','aria-valuemax','aria-valuenow','aria-valuetext','aria-orientation']) button.removeAttribute(name);
    } else {
      button.removeAttribute('aria-pressed');
      button.setAttribute('aria-valuemin',stops[index-1][0]+1);
      button.setAttribute('aria-valuemax',stops[index+1][0]-1);
      button.setAttribute('aria-valuenow',value[0]);
      button.setAttribute('aria-valuetext',`${value[0]}%`);
      button.setAttribute('aria-orientation','horizontal');
    }
  });
  drawGradient(stops);
  const endpoint = selectedStop === 0 || selectedStop === stops.length-1;
  $('stop-position-value').textContent = `${stop[0]}%${endpoint ? ' (endpoint)' : ''}`;
  const last = selectedStop === stops.length-1;
  $('fade-midpoint').disabled = !connected || last;
  $('fade-midpoint').value = stop[4]; $('fade-midpoint-value').textContent = last ? 'No next stop' : `${stop[4]}%`;
  $('remove-stop').disabled = !connected || endpoint;
  $('add-stop').disabled = !connected || stops.length >= 6;
}
function moveStop(index,position) {
  change(() => {
    const gradient=gradientStops().map(stop=>[...stop]);
    if (index <= 0 || index >= gradient.length-1) throw new Error('Gradient endpoints stay fixed.');
    const low=gradient[index-1][0]+1,high=gradient[index+1][0]-1;
    const value=typeof position === 'function' ? position(gradient[index][0],low,high) : position;
    gradient[index][0]=Math.max(low,Math.min(high,Math.round(value)));
    return {gradient};
  });
}
function startStopDrag(event,index) {
  if (!connected || event.button !== 0 || stopDrag) return;
  event.preventDefault(); selectedStop=index; renderPalette();
  const button=$('gradient-stops').children[index]; button.focus({preventScroll:true});
  const stops=gradientStops();
  if (index === 0 || index === stops.length-1) return;
  stopDrag={index,pointer:event.pointerId,startX:event.clientX,start:stops[index][0],position:stops[index][0],
    width:$('gradient-bar').getBoundingClientRect().width,stops:stops.map(stop=>[...stop]),button};
  button.setPointerCapture(event.pointerId);
}
function moveStopDrag(event) {
  if (!stopDrag || event.pointerId !== stopDrag.pointer) return;
  const drag=stopDrag;
  const low=drag.stops[drag.index-1][0]+1,high=drag.stops[drag.index+1][0]-1;
  drag.position=Math.max(low,Math.min(high,Math.round(drag.start+(event.clientX-drag.startX)*100/drag.width)));
  drag.stops[drag.index][0]=drag.position;
  drag.button.style.left=`${drag.position}%`;
  drag.button.setAttribute('aria-valuenow',drag.position); drag.button.setAttribute('aria-valuetext',`${drag.position}%`);
  $('stop-position-value').textContent=`${drag.position}%`;
  drawGradient(drag.stops);
}
function finishStopDrag(event,cancel) {
  if (!stopDrag || (event && event.pointerId !== stopDrag.pointer)) return;
  const drag=stopDrag; stopDrag=null;
  if (drag.button.hasPointerCapture(drag.pointer)) drag.button.releasePointerCapture(drag.pointer);
  if (!cancel && connected && drag.position !== drag.start) {
    lastStopDrag={index:drag.index,time:performance.now()};
    moveStop(drag.index,drag.position);
  } else renderPalette();
}
function updateStop(edit) {
  const index = selectedStop;
  change(() => {
    const gradient = gradientStops().map(stop => [...stop]);
    edit(gradient[index]); return {gradient};
  });
}
$('color-mode').addEventListener('change', event => change({color_mode:event.target.value}));
for (const [id, column] of [['fade-midpoint',4]]) {
  $(id).addEventListener('input', event => {
    $(id+'-value').textContent = `${event.target.value}%`;
    const stops = gradientStops().map(stop => [...stop]); stops[selectedStop][column] = Number(event.target.value);
    drawGradient(stops);
  });
  $(id).addEventListener('change', event => {
    const value = Number(event.target.value);
    updateStop(stop => { stop[column] = value; });
  });
}
$('add-stop').addEventListener('click', () => {
  change(() => {
    const gradient = gradientStops().map(stop => [...stop]);
    if (gradient.length >= 6) throw new Error('A gradient can have up to six color stops.');
    let gap = 0;
    for (let i=1; i<gradient.length-1; i++) {
      if (gradient[i+1][0]-gradient[i][0] > gradient[gap+1][0]-gradient[gap][0]) gap=i;
    }
    const left=gradient[gap], right=gradient[gap+1];
    const position=Math.floor((left[0]+right[0])/2);
    const fraction=(position-left[0])/(right[0]-left[0]), midpoint=left[4]/100;
    const mix=fraction<=midpoint ? .5*fraction/midpoint : .5+.5*(fraction-midpoint)/(1-midpoint);
    const rgb=left.slice(1,4).map((v,c)=>Math.round(v+(right[c+1]-v)*mix));
    gradient.splice(gap+1,0,[position,...rgb,50]); selectedStop=gap+1; return {gradient};
  });
});
$('remove-stop').addEventListener('click', () => {
  const index = selectedStop;
  change(() => {
    const gradient = gradientStops().map(stop => [...stop]);
    if (index === 0 || index >= gradient.length-1) throw new Error('Gradient endpoints cannot be removed.');
    gradient.splice(index,1); selectedStop=Math.max(0,index-1); return {gradient};
  });
});
function renderSchedule(schedule, effective) {
  $('effective-brightness').textContent = typeof effective === 'number' ? `${(effective * 100).toFixed(1)}%` : 'not reported';
  if (settings.automatic === false) { $('schedule-note').textContent = 'Manual control. Automatic sleep and dimming are off.'; return; }
  if (!schedule) { $('schedule-note').textContent = 'Sunset on, sunrise off, with late-night dimming. Waiting for board status.'; return; }
  if (schedule.phase === 'waiting for clock') { $('schedule-note').textContent = 'Waiting for clock sync. Automatic output stays off.'; return; }
  if (schedule.phase === 'location required') { $('schedule-note').textContent = 'Set LATITUDE and LONGITUDE in settings.toml, then restart. Manual lighting remains available; automatic sleep is off.'; return; }
  if (schedule.phase === 'solar unavailable') { $('schedule-note').textContent = 'No daily sunrise/sunset cycle near this date. Manual lighting remains available; automatic sleep and dimming are off. The schedule retries daily.'; return; }
  let formatter;
  try {
    formatter = new Intl.DateTimeFormat('en-US', {timeZone:schedule.timezone || 'UTC',hour:'numeric',minute:'2-digit'});
  } catch (error) {
    if (!(error instanceof RangeError)) throw error;
    $('schedule-note').textContent = 'Invalid TIMEZONE in settings.toml. Use an IANA name such as America/New_York, then restart. Solar timing still uses your coordinates.';
    return;
  }
  const local = stamp => typeof stamp === 'number' ? formatter.format(new Date(stamp * 1000)) : 'the next solar event';
  $('schedule-note').textContent = schedule.phase === 'day' ? `Daytime: lights off. Next start at ${local(schedule.next_sunset)}.` : schedule.phase === 'manual wake' ? `Manual wake. Daytime lights enabled until ${local(schedule.next_sunrise)}.` : `Sunset schedule active. Lights off at ${local(schedule.next_sunrise)}. Brightness fades to 50% after 2 hours and 25% after 4 hours.`;
}
async function readSerial() {
  let buffer = '';
  const decoder = new TextDecoder();
  try {
    while (port?.readable) {
      const { value, done } = await reader.read(); if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        const raw = buffer.slice(0, newline); buffer = buffer.slice(newline + 1);
        let message; try { message = JSON.parse(raw); } catch { continue; }
        if (message.event === 'frame' && connected && !pendingChanges) {
          settings = message.settings; renderSchedule(message.schedule, message.effective_brightness);
        } else if (pending.has(message.id)) {
          const entry = pending.get(message.id); pending.delete(message.id); clearTimeout(entry.timer);
          if (message.ok) entry.resolve(message); else entry.reject(new Error(message.error));
        }
      }
      if (buffer.length > 8192) throw new Error('Unexpected serial output. Check the installed controller firmware.');
    }
  } catch (error) { if (!disconnecting) notice(`USB connection lost: ${error.message}`, true); }
  finally { if (!disconnecting) { notice('USB disconnected. The board keeps its current show while powered.', true); await disconnect(); } }
}
async function disconnect() {
  if (disconnecting) return;
  disconnecting = true; connected = false;
  discardLiveColor();
  wifiEnabled = false; wifiBusy = false; wifiFailures = 0; wifiGeneration++;
  wifiAbort?.abort(); wifiAbort = null;
  clearTimeout(wifiTimer);
  for (const p of pending.values()) { clearTimeout(p.timer); p.reject(new Error('USB disconnected.')); } pending.clear();
  try { await reader?.cancel(); } catch { /* The device may already be unplugged. */ }
  try { reader?.releaseLock(); writer?.releaseLock(); await port?.close(); } catch { /* A removed port is already closed. */ }
  reader = null; writer = null; port = null; disconnecting = false;
  $('connection-status').textContent = 'No board connected'; sync();
  $('schedule-note').textContent = 'Connect to read the board’s schedule.'; $('effective-brightness').textContent = 'not connected';
}
$('connect').addEventListener('click', async () => {
  if (connected) { await disconnect(); notice('Controls disconnected. The board keeps running while powered.'); return; }
  if (boardWebsite) { await connectWifi(); return; }
  if (!navigator.serial?.requestPort) { notice('USB control needs Chrome or Edge on desktop. You can use http://halloween.local over Wi-Fi in other browsers.', true); return; }
  usbBusy = true; renderConnection();
  try {
    sync(); notice('Choose the Feather data interface in the USB dialog.');
    transport = 'usb';
    port = await navigator.serial.requestPort({filters: [{usbVendorId: 0x239a}]});
    await port.open({baudRate: 115200});
    await port.setSignals?.({dataTerminalReady: true});
    reader = port.readable.getReader(); writer = port.writable.getWriter();
    void readSerial(); notice('Connecting to the board…');
    const hello = await request('hello');
    if (hello.device !== 'halloween-leds' || hello.protocol !== 1) throw new Error('This is not the Halloween controller firmware.');
    connected = true; settings = hello.settings; $('brightness').max = hello.limit * 100;
    $('ota-address').textContent = hello.ota_url ? `Board OTA address: ${hello.ota_url}` : 'The board has no Wi-Fi address yet. Check its private settings.toml and network connection.';
    $('connection-status').textContent = 'Feather connected over USB';
    notice('Connected. Controls now change the actual LEDs.'); sync();
    renderSchedule(hello.schedule, hello.effective_brightness);
  } catch (error) { await disconnect(); notice(error.name === 'NotFoundError' ? 'No USB port selected. Connect again when ready.' : error.message, true); }
  finally { usbBusy = false; renderConnection(); }
});
$('brightness').addEventListener('input', event => { $('brightness-value').textContent = `${event.target.value}%`; });
$('brightness').addEventListener('change', event => change({brightness: Number(event.target.value) / 100}));
$('speed').addEventListener('input', event => { $('speed-value').textContent = `${Number(event.target.value).toFixed(2)}×`; });
$('speed').addEventListener('change', event => change({speed: Number(event.target.value)}));
function discardLiveColor() {
  clearTimeout(colorTimer); colorTimer=null; colorDraft=null; colorBusy=false; colorJob++; lastColorCommit=null;
}
function colorCommitKey(source,index,rgb) { return `${source}:${index}:${hex(rgb)}`; }
function stageLiveColor(value,commit=false) {
  if (!connected) return;
  const rgb=[1,3,5].map(i=>parseInt(value.slice(i,i+2),16));
  const source=commit && colorDraft ? colorDraft.source : settings.color_mode === 'gradient' ? 'gradient' : 'solid';
  const index=commit && colorDraft ? colorDraft.index : selectedStop;
  const current=source === 'gradient' ? gradientStops()[index]?.slice(1,4) : settings.color;
  if (!current) return;
  if (!colorDraft && hex(current) === value && (!commit || lastColorCommit === colorCommitKey(source,index,rgb))) return;
  if (colorDraft?.commit && hex(colorDraft.rgb) === value) return;
  colorDraft={source,index,rgb,commit,version:++colorVersion};
  renderPalette();
  if (commit) { clearTimeout(colorTimer); colorTimer=null; void flushLiveColor(); }
  else if (!colorBusy && colorTimer === null) colorTimer=setTimeout(flushLiveColor,150);
}
async function flushLiveColor() {
  colorTimer=null;
  if (colorBusy || !colorDraft || !connected) return;
  colorBusy=true;
  const draft={...colorDraft,rgb:[...colorDraft.rgb]},job=++colorJob;
  const applied=await change(()=>{
    if (draft.source === 'solid') return {color:draft.rgb};
    const gradient=gradientStops().map(stop=>[...stop]);
    if (!gradient[draft.index]) throw new Error('The selected gradient stop no longer exists.');
    gradient[draft.index].splice(1,3,...draft.rgb); return {gradient};
  },{persist:draft.commit,quiet:!draft.commit});
  if (job !== colorJob) return;
  colorBusy=false;
  if (!applied) { discardLiveColor(); renderPalette(); return; }
  if (draft.commit) lastColorCommit=colorCommitKey(draft.source,draft.index,draft.rgb);
  if (colorDraft?.version === draft.version && draft.commit) { colorDraft=null; renderPalette(); }
  else if (colorDraft && colorDraft.version !== draft.version) colorTimer=setTimeout(flushLiveColor,colorDraft.commit?0:150);
}
$('color').addEventListener('input', event => stageLiveColor(event.target.value));
$('color').addEventListener('change', event => stageLiveColor(event.target.value,true));
$('color').addEventListener('blur', () => { if (colorDraft && !colorDraft.commit) stageLiveColor(hex(colorDraft.rgb),true); });
$('blackout').addEventListener('click', () => change({blackout: !settings.blackout}));
$('automatic').addEventListener('change', event => change({automatic:event.target.checked,blackout:false}));
$('save').addEventListener('click', () => {
  const generation = wifiGeneration;
  commandQueue = commandQueue.then(async () => { if (connected && generation === wifiGeneration) { await request('save'); notice('Startup settings saved on the board. They will survive a power cycle.'); } }).catch(error => notice(error.message, true));
});
function recoverWifi() {
  if (!wifiEnabled) return;
  connected = false; wifiBusy = false; wifiGeneration++;
  discardLiveColor();
  wifiAbort?.abort(); wifiAbort = null;
  clearTimeout(wifiTimer);
  $('connection-status').textContent = 'Connection lost; reconnecting';
  sync();
  $('effective-brightness').textContent = 'connection lost';
  notice('Wi-Fi connection lost. Reconnecting automatically. The board keeps running while powered.', true);
  wifiTimer = setTimeout(connectWifi, 3000);
}
$('reconnect').addEventListener('click', () => { void connectWifi(); });
async function connectWifi() {
  wifiEnabled = true; transport = 'wifi';
  const generation = ++wifiGeneration;
  wifiAbort?.abort(); clearTimeout(wifiTimer);
  const controller = new AbortController(); wifiAbort = controller;
  const timeout = setTimeout(() => controller.abort(), WIFI_TIMEOUT_MS);
  wifiBusy = true; connected = false; sync();
  $('connection-status').textContent = 'Connecting over Wi-Fi…';
  notice('Connecting to the lights over Wi-Fi…');
  try {
    const response = await fetch('/api/state', {cache:'no-store', signal:controller.signal});
    if (!response.ok) throw new Error(`The board returned HTTP ${response.status}.`);
    const state = await response.json();
    if (generation !== wifiGeneration || !wifiEnabled) return;
    if (state.device !== 'halloween-leds' || state.protocol !== 1) throw new Error('Unexpected controller response.');
    connected = true; wifiBusy = false; wifiFailures = 0; settings = state.settings;
    $('brightness').max = state.limit * 100;
    $('connection-status').textContent = 'Lights connected over Wi-Fi';
    $('ota-address').textContent = state.ota_url ? `Board OTA address: ${state.ota_url}` : 'OTA service is unavailable.';
    sync(); renderSchedule(state.schedule, state.effective_brightness);
    notice('Connected over Wi-Fi. Controls now change the actual LEDs.');
    wifiTimer = setTimeout(pollWifi, 2000);
  } catch (error) {
    if (generation === wifiGeneration && wifiEnabled) recoverWifi();
  } finally {
    clearTimeout(timeout);
    if (generation === wifiGeneration) { wifiBusy = false; wifiAbort = null; renderConnection(); }
  }
}
async function pollWifi() {
  if (!connected || transport !== 'wifi' || !wifiEnabled) return;
  if (pendingChanges) { wifiTimer = setTimeout(pollWifi, 2000); return; }
  const revision = stateRevision;
  const generation = wifiGeneration;
  try {
    const response = await fetch('/api/state', {cache:'no-store',signal:AbortSignal.timeout(WIFI_TIMEOUT_MS)});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const state = await response.json();
    if (!connected || generation !== wifiGeneration) return;
    if (pendingChanges || revision !== stateRevision) { wifiTimer = setTimeout(pollWifi, 2000); return; }
    const changed = JSON.stringify(settings) !== JSON.stringify(state.settings);
    const wasDelayed = wifiFailures > 0;
    wifiFailures = 0;
    settings = state.settings;
    if (changed && !document.activeElement.matches('input, select')) sync();
    renderSchedule(state.schedule, state.effective_brightness);
    if (wasDelayed) {
      $('connection-status').textContent = 'Lights connected over Wi-Fi'; renderConnection();
      notice('Wi-Fi connection restored.');
    }
    wifiTimer = setTimeout(pollWifi, 2000);
  } catch (error) {
    if (generation !== wifiGeneration || !wifiEnabled) return;
    wifiFailures++;
    if (wifiFailures >= 2) recoverWifi();
    else {
      $('connection-status').textContent = 'Wi-Fi delayed; retrying'; renderConnection();
      notice('The board is slow to respond. Retrying the connection…', true);
      wifiTimer = setTimeout(pollWifi, 2000);
    }
  }
}
sync();
if (boardWebsite) void connectWifi();
