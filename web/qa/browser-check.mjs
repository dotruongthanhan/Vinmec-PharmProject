// Kiểm tra bằng Chromium cục bộ, chỉ dùng dữ liệu giả lập và mô-đun có sẵn.
import { spawn } from 'node:child_process'
import { mkdir, writeFile, mkdtemp, rm } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { tmpdir } from 'node:os'

const phase = process.argv[2] ?? 'a'
const output = resolve('qa/artifacts', phase)
await mkdir(output, { recursive: true })
const profile = await mkdtemp(resolve(tmpdir(), 'pharm-qa-'))
const child = spawn('C:/Users/Admin/AppData/Local/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe', [
  '--headless', '--enable-begin-frame-control', '--run-all-compositor-stages-before-draw', '--disable-gpu', '--in-process-gpu', '--no-sandbox', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank',
], { windowsHide: true, stdio: ['ignore', 'ignore', 'pipe'] })
let socket
try {
  const endpoint = await new Promise((ok, fail) => {
    let log = ''
    const timeout = setTimeout(() => fail(new Error('Chromium chưa sẵn sàng')), 15000)
    child.stderr.on('data', (chunk) => {
      log += chunk.toString()
      const match = /DevTools listening on (ws:\/\/[^\s]+)/.exec(log)
      if (match) { clearTimeout(timeout); ok(match[1]) }
    })
    child.on('error', fail)
  })
  socket = new WebSocket(endpoint)
  await new Promise((ok, fail) => { socket.onopen = ok; socket.onerror = fail })
  let nextId = 0
  const pending = new Map()
  const errors = []
  let onLoad
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data)
    if (message.id) {
      const request = pending.get(message.id)
      pending.delete(message.id)
      if (message.error) request.reject(new Error(message.error.message))
      else request.resolve(message.result)
    } else if (message.method === 'Page.loadEventFired') {
      onLoad?.()
      onLoad = undefined
    } else if (message.method === 'Runtime.exceptionThrown') {
      errors.push(message.params.exceptionDetails.text)
    }
  }
  socket.onclose = ({ code, reason }) => {
    for (const request of pending.values()) request.reject(new Error(`Chromium đóng kết nối: ${code} ${reason}`))
  }
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++nextId
    const timeout = setTimeout(() => reject(new Error(`Quá thời gian: ${method}`)), 15000)
    pending.set(id, { resolve: (result) => { clearTimeout(timeout); resolve(result) }, reject: (error) => { clearTimeout(timeout); reject(error) } })
    socket.send(JSON.stringify({ id, method, params, sessionId }))
  })
  const { targetId } = await send('Target.createTarget', { url: 'about:blank', enableBeginFrameControl: true, width: 1440, height: 900 })
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
  const command = (method, params) => send(method, params, sessionId)
  await command('Page.enable')
  await command('Runtime.enable')
  await command('Page.bringToFront')
  await command('Page.addScriptToEvaluateOnNewDocument', {source:`(() => {
    const observer=new MutationObserver(() => {
      if (document.getElementById('root')?.firstChild) {
        window.pharmQaFirstRenderTheme=document.documentElement.dataset.theme;
        observer.disconnect();
      }
    });
    observer.observe(document,{childList:true,subtree:true});
  })()`})
  const evaluate = async (expression) => {
    const result = await command('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails))
    return result.result.value
  }
  const waitFor = async (expression) => {
    for (let attempt = 0; attempt < 100; attempt++) {
      try { if (await evaluate(expression)) return } catch { /* Trang đang chuyển tài liệu. */ }
      await command('HeadlessExperimental.beginFrame')
      await new Promise((ok) => setTimeout(ok, 50))
    }
    throw new Error(`Không thấy: ${expression}`)
  }
  const navigate = async (path, condition) => {
    const loaded = new Promise((ok) => { onLoad = ok })
    await command('Page.navigate', { url: `http://127.0.0.1:5173${path}` })
    await loaded
    await waitFor(condition)
    await evaluate('document.fonts.ready.then(() => true)')
  }
  const clickText = async (text) => {
    const expression = `Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === ${JSON.stringify(text)})`
    await waitFor(`Boolean(${expression})`)
    await evaluate(`${expression}.click()`)
  }
  const clickSelector = async (selector) => {
    const point = await evaluate(`(() => { const r=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
    await command('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...point })
    await command('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...point })
  }
  const chooseTheme = async (preference) => {
    let openedSidebar = false
    const group = `[...document.querySelectorAll('[aria-label="Chế độ sáng tối"]')].find(el=>el.getClientRects().length && !el.closest('[data-state="closed"]'))`
    if (!await evaluate(`Boolean(${group})`)) {
      await clickSelector('button[aria-label="Mở thanh điều hướng"]')
      openedSidebar = true
      await waitFor(`Boolean(${group})`)
      await capture('sidebar-theme-control')
    }
    const label = {light:'Sáng',dark:'Tối',system:'Theo hệ thống'}[preference]
    const point = await evaluate(`(() => { const group=${group}; const b=[...group.querySelectorAll('button')].find(b=>b.textContent===${JSON.stringify(label)}); const r=b.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2} })()`)
    await command('Input.dispatchMouseEvent', { type:'mousePressed', button:'left', clickCount:1, ...point })
    await command('Input.dispatchMouseEvent', { type:'mouseReleased', button:'left', clickCount:1, ...point })
    const expected = preference === 'system' ? 'dark' : preference
    await waitFor(`document.documentElement.dataset.theme === '${expected}'`)
    if (openedSidebar) {
      await command('Input.dispatchKeyEvent', { type:'keyDown', key:'Escape', code:'Escape', windowsVirtualKeyCode:27 })
      await command('Input.dispatchKeyEvent', { type:'keyUp', key:'Escape', code:'Escape', windowsVirtualKeyCode:27 })
      await waitFor("!document.querySelector('[role=\"dialog\"][data-state=\"open\"]')")
    }
  }
  const themeResults = []
  const reviewThemes = async (name) => {
    if (phase !== 'b') return
    await command('Emulation.setEmulatedMedia', { features: [{name:'prefers-reduced-motion',value:'reduce'}, {name:'prefers-color-scheme',value:'dark'}] })
    for (const preference of ['light','dark','system']) {
      await chooseTheme(preference)
      await capture(`${name}-${preference}`)
      themeResults.push({name, preference, ...await evaluate(`({theme:document.documentElement.dataset.theme, scheme:getComputedStyle(document.documentElement).colorScheme, meta:document.querySelector('meta[name="theme-color"]').content, canvas:getComputedStyle(document.documentElement).getPropertyValue('--color-canvas').trim(), path:location.pathname})`)})
    }
    await command('Emulation.setEmulatedMedia', { features: [{name:'prefers-reduced-motion',value:'reduce'}, {name:'prefers-color-scheme',value:'light'}] })
    await waitFor("document.documentElement.dataset.theme === 'light'")
    await command('Emulation.setEmulatedMedia', { features: [{name:'prefers-reduced-motion',value:'reduce'}, {name:'prefers-color-scheme',value:'dark'}] })
    await waitFor("document.documentElement.dataset.theme === 'dark'")
    await chooseTheme('dark')
  }
  const capture = async (name) => {
    await waitFor("document.readyState === 'complete' && Boolean(document.body?.children.length)")
    await evaluate('document.fonts.ready.then(() => true)')
    for (let frame = 0; frame < 5; frame++) {
      await command('HeadlessExperimental.beginFrame')
      await new Promise((ok) => setTimeout(ok, 50))
    }
    let data
    for (let attempt = 0; attempt < 10 && !data; attempt++) {
      const result = await command('HeadlessExperimental.beginFrame', { screenshot: { format: 'png' } })
      data = result.screenshotData
      if (!data) await new Promise((ok) => setTimeout(ok, 50))
    }
    await writeFile(resolve(output, `${name}.png`), Buffer.from(data, 'base64'))
  }
  const results = []
  for (const width of process.argv[3] ? [Number(process.argv[3])] : [1440, 1180, 900, 390]) {
    await command('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: false })
    await command('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
    await navigate('/', "Boolean(document.querySelector('h1'))")
    await evaluate("sessionStorage.removeItem('pharm_review_demo')")
    await reviewThemes(`landing-${width}`)
    await capture(`landing-${width}`)
    results.push({ width, screen: 'landing', ...(await evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')) })
    await navigate('/dang-nhap', "document.body.textContent.includes('Vào bản demo')")
    await reviewThemes(`login-${width}`)
    await capture(`login-${width}`)
    await clickText('Vào bản demo')
    await waitFor("Boolean(document.querySelector('table[aria-label=\"Danh sách y lệnh\"] tbody tr'))")
    await reviewThemes(`orders-${width}`)
    if (phase === 'b' && width === 1440) {
      await clickSelector('input[aria-label="Tìm kiếm y lệnh"]')
      await command('Input.insertText', {text:'MEROPENEM'})
      await waitFor("document.querySelectorAll('table[aria-label=\"Danh sách y lệnh\"] tbody tr').length === 1")
      await reviewThemes('orders-filter')
      if (!await evaluate("document.querySelector('input[aria-label=\"Tìm kiếm y lệnh\"]').value === 'MEROPENEM'")) throw new Error('Đổi màu làm mất bộ lọc')
      await clickSelector('button[aria-label="Xoá từ khoá tìm kiếm"]')
    }
    await capture(`orders-${width}`)
    results.push({ width, screen: 'orders', ...(await evaluate(`(() => {
      const t=document.querySelector('table[aria-label="Danh sách y lệnh"]');
      return { width:innerWidth, scroll:document.documentElement.scrollWidth, table:t.clientWidth, tableScroll:t.scrollWidth, rows:[...t.tBodies[0].rows].map(r=>r.getBoundingClientRect().height) }
    })()`)) })
    await navigate('/app/y-lenh/DEMO-02', "Boolean(document.querySelector('[aria-label=\"Sáu yếu tố thẩm định\"]'))")
    await reviewThemes(`detail-${width}`)
    await capture(`detail-${width}`)
    const reloaded = new Promise((ok) => { onLoad = ok })
    await command('Page.reload')
    await reloaded
    await waitFor("Boolean(document.querySelector('[aria-label=\"Sáu yếu tố thẩm định\"]'))")
    if (phase === 'b') {
      if (!await evaluate("document.documentElement.dataset.theme === 'dark' && window.pharmQaFirstRenderTheme === 'dark'")) throw new Error('Tải lại nháy sai màu')
      await capture(`reload-dark-${width}`)
    }
    results.push({ width, screen: 'detail', ...(await evaluate(`({ path:location.pathname, width:innerWidth, scroll:document.documentElement.scrollWidth, breadcrumb:document.querySelector('nav[aria-label="Đường dẫn"]').textContent, factors:[...document.querySelector('[aria-label="Sáu yếu tố thẩm định"]').children].map(b=>({height:b.clientHeight,text:b.textContent})) })`)) })
    if (width < 1180) {
      await evaluate("document.querySelector('button[aria-label=\"Mở trợ lý\"]').click()")
      await waitFor("Boolean(document.querySelector('[role=\"dialog\"]'))")
    }
    await capture(`assistant-${width}`)
    if (width < 1180) await command('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
    if (width === 1440) {
      await clickSelector('[role="tab"][id$="trigger-xet_nghiem"]')
      await waitFor("Boolean(document.querySelector('svg[role=\"img\"]'))")
      const labels = await evaluate(`(() => { const svg=document.querySelector('svg[role="img"]'); const scale=svg.getBoundingClientRect().width/svg.viewBox.baseVal.width; return [...svg.querySelectorAll('text')].map(t=>parseFloat(getComputedStyle(t).fontSize)*scale) })()`)
      if (Math.min(...labels) < 11) throw new Error(`Chữ biểu đồ nhỏ hơn 11px: ${Math.min(...labels)}`)
      await capture('labs-1440')
      if (phase === 'b') {
        await reviewThemes('labs-1440')
        await clickSelector('[role="tab"][id$="trigger-tham_dinh"]')
        await waitFor("document.body.textContent.includes('AI đã phân tích xong')")
        await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent.trim()==='Mở nguồn')")
        for (const mode of ['light','dark']) {
          await chooseTheme(mode)
          await clickText('Mở nguồn')
          await waitFor("Boolean(document.querySelector('[role=\"dialog\"] mark'))")
          await capture(`source-dialog-${mode}`)
          await command('Input.dispatchKeyEvent', {type:'keyDown', key:'Escape', code:'Escape', windowsVirtualKeyCode:27})
          await command('Input.dispatchKeyEvent', {type:'keyUp', key:'Escape', code:'Escape', windowsVirtualKeyCode:27})
        }
        await clickSelector('textarea[aria-label="Nhập câu hỏi về ca đang mở"]')
        await command('Input.insertText', {text:'Vì sao cần xem lại liều meropenem?'})
        await clickSelector('button[aria-label="Gửi câu hỏi"]')
        await waitFor("Boolean(document.querySelector('button[aria-label^=\"Mở trích dẫn\"]'))")
        await reviewThemes('assistant-conversation')
        if (!await evaluate("document.body.textContent.includes('Vì sao cần xem lại liều meropenem?')")) throw new Error('Đổi màu làm mất hội thoại')
        await clickSelector('button[aria-label^="Mở trích dẫn [2]"]')
        await waitFor("Boolean(document.querySelector('[role=\"tabpanel\"][data-state=\"active\"] mark'))")
        await capture('assistant-source-dark')
        await clickSelector('button[aria-label="Thu gọn thanh điều hướng"]')
        for (const mode of ['light','dark']) {
          await clickSelector('button[aria-label="Chọn chế độ sáng tối"]')
          await waitFor("Boolean(document.querySelector('[aria-label=\"Chế độ sáng tối\"]'))")
          await chooseTheme(mode)
          await capture(`sidebar-collapsed-${mode}`)
          await clickSelector('button[aria-label="Chọn chế độ sáng tối"]')
          await waitFor("!document.querySelector('[role=\"dialog\"][data-state=\"open\"]')")
        }
        await clickSelector('button[aria-label="Mở rộng thanh điều hướng"]')
      }
    }
  }
  const issues = results.filter((result) => result.scroll > result.width || (result.table && result.tableScroll > result.table) || (result.factors && new Set(result.factors.map(f=>f.height)).size !== 1))
  if (themeResults.some(r => r.meta !== r.canvas || r.theme !== r.scheme)) throw new Error('Màu trình duyệt chưa đồng bộ')
  await writeFile(resolve(output, 'layout.json'), JSON.stringify({ results, themeResults, errors, issues }, null, 2))
  console.log(JSON.stringify({ output, screens:results.length, themes:themeResults.length, errors, issues }, null, 2))
  if (issues.length || errors.length) throw new Error('Kiểm tra giao diện chưa đạt')
  await send('Browser.close')
} finally {
  socket?.close()
  child.kill()
  if (dirname(profile) === resolve(tmpdir()) && profile.startsWith(resolve(tmpdir(), 'pharm-qa-'))) {
    await rm(profile, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }).catch(() => {})
  }
}
