import { test, expect } from '@playwright/test';

async function dragStop(page,index,position) {
  const handle=page.locator('#gradient-stops button').nth(index);
  await handle.scrollIntoViewIfNeeded();
  const box=await handle.boundingBox(),rail=await page.locator('#gradient-bar').boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
  await page.mouse.down();await page.mouse.move(rail.x+rail.width*position/100,box.y+box.height/2,{steps:8});await page.mouse.up();
}

async function connectMockBoard(page, delay=0) {
  let settings={mode:'embers',brightness:.15,speed:1,color:[255,65,0],color_mode:'solid',gradient:[[0,255,65,0,50],[100,125,15,240,50]],blackout:false};
  const commands=[];
  let available=true,reads=0;
  await page.route('**/api/**', async route=>{
    if(route.request().method()==='GET')reads++;
    if(!available) { await route.abort('failed'); return; }
    if(route.request().method()==='POST') {
      const command=route.request().postDataJSON();
      if(delay) await new Promise(resolve=>setTimeout(resolve,delay));
      commands.push(command);
      if(command.command==='set')settings={...settings,...command.settings};
    }
    await route.fulfill({json:{ok:true,device:'halloween-leds',protocol:1,settings,limit:1,active:settings.mode,remaining:0,
      effective_brightness:settings.blackout?0:settings.brightness*.25,
      schedule:{phase:'night',factor:.25,timezone:'America/Los_Angeles',next_sunrise:1792506120}}});
  });
  await page.goto('/?wifi=1');
  await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
  return {settings:()=>settings,commands,setAvailable:value=>{available=value;},reads:()=>reads};
}

test('live board controls: every scene, slider, color, blackout and disclosure works', async ({ page }) => {
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await connectMockBoard(page);
  await expect(page.locator('#simulate')).toHaveCount(0);
  await expect(page.locator('.stage, .pixel, .stick, #preview-kind')).toHaveCount(0);
  await expect(page.locator('[data-mode="show"]')).toHaveCount(0);
  for (const mode of ['embers', 'cauldron', 'ghost', 'chase', 'breathing', 'solid']) {
    await page.locator(`[data-mode="${mode}"]`).click();
    await expect(page.locator(`[data-mode="${mode}"]`)).toHaveAttribute('aria-pressed', 'true');
  }
  await page.locator('#brightness').fill('100'); await page.locator('#brightness').dispatchEvent('change');
  await expect(page.locator('#brightness-value')).toHaveText('100%');
  await page.locator('#speed').fill('2'); await page.locator('#speed').dispatchEvent('change');
  await expect(page.locator('#speed-value')).toHaveText('2.00×');
  await page.locator('#color').fill('#aabbcc'); await page.locator('#color').dispatchEvent('change');
  await expect(page.locator('#color')).toHaveValue('#aabbcc');
  await page.locator('#blackout').click(); await expect(page.locator('#blackout')).toHaveText('Restore lights');
  await page.locator('#blackout').click(); await expect(page.locator('#blackout')).toHaveText('Blackout');
  await page.locator('#save').click();
  await expect(page.locator('#notice')).toContainText('Startup settings saved');
  for (const summary of await page.locator('summary').all()) { await summary.click(); await expect(summary.locator('..')).toHaveAttribute('open', ''); }
  await page.locator('#connect').click(); await expect(page.locator('#blackout')).toBeDisabled();
  expect(errors).toEqual([]);
});

test('pattern and editable gradient remain independent, including fade points and stop limits', async ({page}) => {
  const board=await connectMockBoard(page);
  await page.locator('[data-mode="chase"]').click();
  await expect(page.locator('[data-mode="chase"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('#color-mode').selectOption('gradient');
  await expect(page.locator('#gradient-editor')).toBeVisible();
  await expect(page.locator('#stop-position')).toHaveCount(0);
  await expect(page.locator('#remove-stop')).toBeDisabled();
  await page.locator('#add-stop').click();
  await expect(page.locator('#gradient-stops button')).toHaveCount(3);
  await expect(page.locator('#stop-position-value')).toHaveText('50%');
  await dragStop(page,1,35);
  await expect(page.locator('#stop-position-value')).toHaveText('35%');
  await page.locator('#color').fill('#00ff00'); await page.locator('#color').dispatchEvent('change');
  await page.locator('#fade-midpoint').fill('25'); await page.locator('#fade-midpoint').dispatchEvent('change');
  await expect.poll(()=>board.settings().gradient[1]).toEqual([35,0,255,0,25]);
  await expect(page.locator('[data-mode="chase"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('#gradient-stops button').last().click();
  await expect(page.locator('#fade-midpoint')).toBeDisabled();
  await expect(page.locator('#remove-stop')).toBeDisabled();
  for(let count=4;count<=6;count++) {
    await page.locator('#add-stop').click();
    await expect(page.locator('#gradient-stops button')).toHaveCount(count);
  }
  await expect(page.locator('#add-stop')).toBeDisabled();
  await page.locator('#remove-stop').click();
  await expect(page.locator('#gradient-stops button')).toHaveCount(5);
  const gradient=structuredClone(board.settings().gradient);
  await page.locator('[data-mode="ghost"]').click();
  await expect.poll(()=>board.settings().mode).toBe('ghost');
  expect(board.settings().gradient).toEqual(gradient);
  await page.locator('#color-mode').selectOption('solid');
  await expect(page.locator('#gradient-editor')).toBeHidden();
  await expect.poll(()=>board.settings().mode).toBe('ghost');
  await page.locator('#color-mode').selectOption('gradient');
  await expect(page.locator('#gradient-stops button')).toHaveCount(5);
  expect(board.settings().gradient).toEqual(gradient);
  await page.locator('[data-mode="breathing"]').click();
  await expect(page.locator('#gradient-note')).toContainText('all LEDs together');
  expect(board.settings().gradient).toEqual(gradient);
  await page.locator('#connect').click();
  await expect(page.locator('#color-mode')).toBeDisabled();
  await expect(page.locator('#add-stop')).toBeDisabled();
});

test('gradient handles drag with one save, clamp to neighbors, cancel, and support keyboard movement', async ({page}) => {
  const board=await connectMockBoard(page);
  await page.locator('#color-mode').selectOption('gradient');await expect(page.locator('#gradient-editor')).toBeVisible();
  await page.locator('#add-stop').click();await expect(page.locator('#gradient-stops button')).toHaveCount(3);
  const handle=page.locator('#gradient-stops button').nth(1);
  await handle.scrollIntoViewIfNeeded();
  let box=await handle.boundingBox();const rail=await page.locator('#gradient-bar').boundingBox();const before=board.commands.length;
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(rail.x+rail.width*.35,box.y+box.height/2,{steps:10});
  await expect(page.locator('#stop-position-value')).toHaveText('35%');
  expect(board.commands.length).toBe(before);
  await page.mouse.up();await expect.poll(()=>board.settings().gradient[1][0]).toBe(35);
  expect(board.commands.length).toBe(before+1);
  await handle.press('ArrowRight');await expect.poll(()=>board.settings().gradient[1][0]).toBe(36);
  await handle.press('Shift+ArrowLeft');await expect.poll(()=>board.settings().gradient[1][0]).toBe(26);
  await handle.press('Home');await expect.poll(()=>board.settings().gradient[1][0]).toBe(1);
  await handle.press('End');await expect.poll(()=>board.settings().gradient[1][0]).toBe(99);
  await expect(handle).toHaveAttribute('role','slider');await expect(handle).toHaveAttribute('aria-valuenow','99');
  await dragStop(page,1,-20);await expect.poll(()=>board.settings().gradient[1][0]).toBe(1);
  await dragStop(page,1,150);await expect.poll(()=>board.settings().gradient[1][0]).toBe(99);
  const saved=board.commands.length;box=await handle.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();await page.mouse.move(rail.x+rail.width*.5,box.y+box.height/2);
  await page.keyboard.press('Escape');await page.mouse.up();
  expect(board.commands.length).toBe(saved);await expect(page.locator('#stop-position-value')).toHaveText('99%');
  await dragStop(page,0,30);await dragStop(page,2,70);
  expect(board.settings().gradient[0][0]).toBe(0);expect(board.settings().gradient[2][0]).toBe(100);
});

test('numbered gradient stops support native touch dragging', async ({page}) => {
  const board=await connectMockBoard(page);
  await page.setViewportSize({width:375,height:812});
  await page.locator('#color-mode').selectOption('gradient');await expect(page.locator('#gradient-editor')).toBeVisible();
  await page.locator('#add-stop').click();await expect(page.locator('#gradient-stops button')).toHaveCount(3);
  const handle=page.locator('#gradient-stops button').nth(1);await handle.scrollIntoViewIfNeeded();
  const box=await handle.boundingBox(),rail=await page.locator('#gradient-bar').boundingBox();
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setTouchEmulationEnabled',{enabled:true});
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+box.width/2,y:box.y+box.height/2}]});
  await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:rail.x+rail.width*.7,y:box.y+box.height/2}]});
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await expect.poll(()=>board.settings().gradient[1][0]).toBe(70);
  await cdp.detach();
});

test('rapid gradient edits merge after delayed board acknowledgments', async ({page}) => {
  const board=await connectMockBoard(page,200);
  await page.locator('#color-mode').selectOption('gradient');
  await expect(page.locator('#gradient-editor')).toBeVisible();
  await page.evaluate(()=>{
    const color=document.getElementById('color'); color.value='#00ff00'; color.dispatchEvent(new Event('change'));
    const midpoint=document.getElementById('fade-midpoint'); midpoint.value='25'; midpoint.dispatchEvent(new Event('change'));
  });
  await expect.poll(()=>board.settings().gradient[0]).toEqual([0,0,255,0,25]);
  await expect(page.locator('#color')).toHaveValue('#00ff00');
  await expect(page.locator('#fade-midpoint')).toHaveValue('25');
});

test('live color input coalesces rapid choices and saves only the final change', async ({page}) => {
  const board=await connectMockBoard(page,250);
  const first=page.waitForRequest(request=>request.url().endsWith('/api/command'));
  await page.evaluate(()=>{const color=document.getElementById('color');color.value='#ff0000';color.dispatchEvent(new Event('input'));});
  await first;
  await page.evaluate(()=>{
    const color=document.getElementById('color');
    for(let i=0;i<40;i++){color.value='#'+i.toString(16).padStart(2,'0')+'00ff';color.dispatchEvent(new Event('input'));}
    color.value='#0000ff';color.dispatchEvent(new Event('input'));
  });
  await expect.poll(()=>board.settings().color).toEqual([0,0,255]);
  await expect(page.locator('#color')).toHaveValue('#0000ff');
  expect(board.commands).toHaveLength(2);
  expect(board.commands.every(command=>command.persist===false)).toBe(true);
  await page.locator('#color').dispatchEvent('change');
  await expect.poll(()=>board.commands.filter(command=>command.persist===true).length).toBe(1);
  await page.locator('#color').dispatchEvent('change');
  expect(board.commands.filter(command=>command.persist===true)).toHaveLength(1);
});

test('gradient stop colors update on input before the picker is closed', async ({page}) => {
  const board=await connectMockBoard(page);
  await page.locator('#color-mode').selectOption('gradient');await expect(page.locator('#gradient-editor')).toBeVisible();
  const before=board.commands.length;
  await page.evaluate(()=>{const color=document.getElementById('color');color.value='#00ff00';color.dispatchEvent(new Event('input'));});
  await expect.poll(()=>board.settings().gradient[0].slice(1,4)).toEqual([0,255,0]);
  expect(board.commands[before].persist).toBe(false);
  expect(board.settings().mode).toBe('embers');
  await page.locator('#color').dispatchEvent('change');
  await expect.poll(()=>board.commands.length).toBe(before+2);
  expect(board.commands.at(-1).persist).toBe(true);
});

test('reconnection does not replay a live color but allows the final color to be saved', async ({page}) => {
  const board=await connectMockBoard(page);
  await page.evaluate(()=>{const color=document.getElementById('color');color.value='#00ff00';color.dispatchEvent(new Event('input'));});
  await expect.poll(()=>board.settings().color).toEqual([0,255,0]);
  expect(board.commands).toHaveLength(1);expect(board.commands[0].persist).toBe(false);
  await page.locator('#connect').click();await page.locator('#reconnect').click();
  await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
  expect(board.commands).toHaveLength(1);
  await page.locator('#color').dispatchEvent('change');
  await expect.poll(()=>board.commands.length).toBe(2);
  expect(board.commands[1].persist).toBe(true);
});

test('slow commands get fifteen seconds instead of timing out after five', async ({page}) => {
  await page.addInitScript(()=>{
    const timeout=AbortSignal.timeout.bind(AbortSignal);window.timeouts=[];
    AbortSignal.timeout=ms=>{window.timeouts.push(ms);return timeout(ms);};
  });
  const board=await connectMockBoard(page,6000);
  await page.locator('[data-mode="chase"]').click();
  await expect(page.locator('[data-mode="chase"]')).toHaveAttribute('aria-pressed','true',{timeout:12000});
  expect(board.commands).toHaveLength(1);
  expect(await page.evaluate(()=>window.timeouts)).toContain(15000);
  await expect(page.locator('#connection-dock')).toBeHidden();
});

test('status failures get a grace retry and then reconnect automatically without replaying commands', async ({page}) => {
  await page.clock.install();
  const board=await connectMockBoard(page);
  board.setAvailable(false);
  await page.clock.runFor(2001);
  await expect(page.locator('#connection-status')).toContainText('delayed');
  await expect(page.locator('#blackout')).toBeEnabled();
  await expect(page.locator('#connection-dock')).toBeVisible();
  await page.clock.runFor(2001);
  await expect(page.locator('#connection-status')).toContainText('reconnecting');
  await expect(page.locator('#blackout')).toBeDisabled();
  board.setAvailable(true);
  await page.clock.runFor(3001);
  await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
  await expect(page.locator('#connection-dock')).toBeHidden();
  expect(board.commands).toEqual([]);
});

test('manual disconnection stays disconnected and the bottom action reconnects without scrolling up', async ({page}) => {
  await page.clock.install();await page.setViewportSize({width:375,height:812});
  const board=await connectMockBoard(page);
  await page.locator('#connect').click();
  const reads=board.reads();await page.clock.runFor(30000);
  expect(board.reads()).toBe(reads);
  await page.evaluate(()=>window.scrollTo(0,document.body.scrollHeight));
  const action=await page.locator('#reconnect').boundingBox();
  expect(action.y).toBeGreaterThan(0);expect(action.y+action.height).toBeLessThanOrEqual(812);
  await page.screenshot({path:'test-results/reconnect-bottom-375.png'});
  await page.locator('#reconnect').click();
  await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
  expect(await page.evaluate(()=>scrollY)).toBeGreaterThan(0);
});

test('an unconfirmed command reconnects by reading state and is not sent twice', async ({page}) => {
  await page.clock.install();
  const board=await connectMockBoard(page);
  let sends=0;
  await page.route('**/api/command',async route=>{sends++;await route.abort('failed');});
  await page.locator('[data-mode="chase"]').click();
  await expect(page.locator('#connection-dock')).toBeVisible();
  await expect(page.locator('#notice')).toContainText('will not be resent');
  await page.clock.runFor(3001);
  await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
  expect(sends).toBe(1);expect(board.commands).toEqual([]);
});

test('USB: handshake, commands, save and disconnect use acknowledged board state', async ({ page }) => {
  await page.addInitScript(() => {
    let controller, settings = {mode:'show',brightness:.15,speed:1,color:[255,65,0],blackout:false};
    window.sent = [];
    const port = {
      async open() { this.readable = new ReadableStream({start(c) {controller = c;}}); this.writable = new WritableStream({write(data) {
        const message = JSON.parse(new TextDecoder().decode(data)); window.sent.push(message);
        if (message.command === 'set') settings = {...settings,...message.settings};
        controller.enqueue(new TextEncoder().encode(JSON.stringify({id:message.id,ok:true,device:'halloween-leds',protocol:1,settings,limit:.25})+'\n'));
      }}); }, async close() {},
    };
    Object.defineProperty(navigator, 'serial', {value:{requestPort:async()=>port},configurable:true});
  });
  await page.goto('/'); await page.locator('#connect').click();
  await expect(page.locator('#connection-status')).toContainText('connected over USB');
  await page.locator('[data-mode="solid"]').click();
  await expect(page.locator('[data-mode="solid"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('#blackout').click(); await expect(page.locator('#blackout')).toHaveText('Restore lights');
  await page.locator('#save').click(); await expect(page.locator('#notice')).toContainText('Startup settings saved');
  expect(await page.evaluate(()=>window.sent.map(x=>x.command))).toEqual(['hello','set','set','save']);
  await page.evaluate(()=>{const color=document.getElementById('color');color.value='#00ff00';color.dispatchEvent(new Event('input'));});
  await expect.poll(()=>page.evaluate(()=>window.sent.at(-1).persist)).toBe(false);
  await page.locator('#color').dispatchEvent('change');
  await expect.poll(()=>page.evaluate(()=>window.sent.at(-1).persist)).toBe(true);
  await page.locator('#connect').click(); await expect(page.locator('#blackout')).toBeDisabled();
});

test('cancelled connection and unsupported browser show useful errors', async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, 'serial', {value:{requestPort:async()=>{throw new DOMException('cancelled','NotFoundError');}},configurable:true}));
  await page.goto('/'); await page.locator('#connect').click();
  await expect(page.locator('#notice')).toContainText('No USB port selected');
  await page.evaluate(()=>Object.defineProperty(navigator,'serial',{value:undefined, configurable:true}));
  await page.locator('#connect').click();
  await expect(page.locator('#notice')).toContainText('needs Chrome or Edge');
});

test('board website connects over Wi-Fi, applies controls, saves, and handles disconnection', async ({ page }) => {
  let settings = {mode:'show',brightness:.15,speed:1,color:[255,65,0],blackout:false};
  const commands = [];
  await page.route('**/api/**', async route => {
    if (route.request().method() === 'POST') {
      const command = route.request().postDataJSON(); commands.push(command.command);
      if (command.command === 'set') settings = {...settings,...command.settings};
    }
    await route.fulfill({json:{ok:true,device:'halloween-leds',protocol:1,settings,limit:.25,pixels:Array(16).fill([255,65,0]),active:'embers',remaining:20,ota_url:'http://halloween.local:8080'}});
  });
  await page.goto('/?wifi=1');
  await expect(page.locator('#connection-status')).toHaveText('Lights connected over Wi-Fi');
  await expect(page.locator('#ota-address')).toContainText('halloween.local:8080');
  await page.locator('[data-mode="cauldron"]').click();
  await expect(page.locator('[data-mode="cauldron"]')).toHaveAttribute('aria-pressed','true');
  await page.locator('#blackout').click(); await expect(page.locator('#blackout')).toHaveText('Restore lights');
  await page.locator('#save').click(); await expect(page.locator('#notice')).toContainText('Startup settings saved');
  expect(commands).toEqual(['set','set','save']);
  await page.locator('#connect').click(); await expect(page.locator('#blackout')).toBeDisabled();
  await page.locator('#connect').click(); await expect(page.locator('#connection-status')).toContainText('connected over Wi-Fi');
});

test('schedule shows daytime blackout and allows acknowledged manual override', async ({ page }) => {
  let settings={mode:'show',brightness:.15,speed:1,color:[255,65,0],blackout:false,automatic:true};
  await page.route('**/api/**', async route=>{
    if(route.request().method()==='POST') {
      const command=route.request().postDataJSON();
      if(command.command==='set')settings={...settings,...command.settings};
    }
    await route.fulfill({json:{ok:true,device:'halloween-leds',protocol:1,settings,limit:.25,
      effective_brightness:settings.automatic?0:.15,
      pixels:Array(16).fill(settings.automatic?[0,0,0]:[255,65,0]),active:'embers',remaining:20,
      schedule:{phase:settings.automatic?'day':'manual',factor:settings.automatic?0:1,timezone:'America/Los_Angeles',next_sunset:1792546020,next_sunrise:1792592520}}});
  });
  await page.goto('/?wifi=1');
  await expect(page.locator('#automatic')).toBeChecked();
  await expect(page.locator('#effective-brightness')).toHaveText('0.0%');
  await expect(page.locator('#schedule-note')).toContainText('Next start at');
  await page.locator('#automatic').uncheck();
  await expect(page.locator('#schedule-note')).toContainText('Manual control');
  await expect(page.locator('#effective-brightness')).toHaveText('15.0%');
  await expect.poll(()=>settings.automatic).toBe(false);
  await page.locator('#automatic').check();
  await expect(page.locator('#effective-brightness')).toHaveText('0.0%');
});

for (const width of [375, 768, 1280]) {
  test(`layout and keyboard at ${width}px`, async ({ page }) => {
    await page.setViewportSize({width,height:1000}); await connectMockBoard(page);
    await page.locator('#color-mode').selectOption('gradient');
    await expect(page.locator('#gradient-editor')).toBeVisible();
    await page.locator('#add-stop').click();
    await expect(page.locator('#gradient-stops button')).toHaveCount(3);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.locator('#blackout').focus(); await page.keyboard.press('Enter');
    await expect(page.locator('#blackout')).toHaveText('Restore lights');
    await page.screenshot({path:`test-results/console-${width}.png`,fullPage:true});
  });
}

for (const [schedule, message] of [
  [{phase:'location required',timezone:'UTC'}, 'Set LATITUDE and LONGITUDE'],
  [{phase:'solar unavailable',timezone:'UTC'}, 'No daily sunrise/sunset cycle'],
  [{phase:'night',timezone:'Not/A_Timezone',next_sunrise:1792506120}, 'Invalid TIMEZONE'],
  [{phase:'night',timezone:'Europe/London',next_sunrise:1792506120}, 'Sunset schedule active']
]) {
  test(`location settings: ${message}`, async ({page}) => {
    const errors=[]; page.on('pageerror', e=>errors.push(e.message));
    await page.route('**/api/**', route=>route.fulfill({json:{ok:true,device:'halloween-leds',protocol:1,
      settings:{mode:'embers',brightness:.15,speed:1,color:[255,65,0],color_mode:'solid',automatic:true,blackout:false},
      limit:1,active:'embers',remaining:0,effective_brightness:.15,schedule}}));
    await page.goto('/?wifi=1');
    await expect(page.locator('#schedule-note')).toContainText(message);
    expect(errors).toEqual([]);
  });
}
