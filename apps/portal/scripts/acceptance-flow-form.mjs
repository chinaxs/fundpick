/** Compile and SSR-render the actual company-action form in selected states. */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const portal = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(resolve(portal, 'package.json'))
const { parse, compileScript } = require('vue/compiler-sfc')
const { createSSRApp } = require('vue')
const { renderToString } = require('vue/server-renderer')
const ts = require('typescript')
const { default: ElementPlus, ID_INJECTION_KEY, ZINDEX_INJECTION_KEY } = require('element-plus')
const source = readFileSync(
  resolve(portal, 'app/components/portfolio/PortfolioFlowsPanel.vue'),
  'utf8',
)

async function render(kind) {
  const { descriptor } = parse(source)
  const script = compileScript(descriptor, { id: 'review-company-action', inlineTemplate: true })
  const code = ts.transpileModule(script.content, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const exports = {}
  const api = () => ({
    listFlows: async () => [],
    addFlow: async () => {},
    removeFlow: async () => {},
  })
  const localRequire = (name) =>
    name === '~/composables/usePortfolioTools'
      ? { portfolioToday: () => '2026-11-09' }
      : require(name)
  new Function('require', 'exports', 'usePortfolioTools', code)(localRequire, exports, api)
  const app = createSSRApp(exports.default, { initialKind: kind })
  app.provide(ID_INJECTION_KEY, { prefix: 1024, current: 0 })
  app.provide(ZINDEX_INJECTION_KEY, { current: 0 })
  app.use(ElementPlus)
  return renderToString(app)
}

const results = []
for (const kind of ['reinvest', 'convert_in', 'convert_out']) {
  const html = await render(kind)
  try {
    if (kind === 'reinvest') {
      assert.match(html, /aria-label="再投金额"/, '页面必须提供再投金额输入')
      assert.match(html, /aria-label="再投份额"/, '页面必须提供再投份额输入')
    } else {
      assert.match(html, /aria-label="转出份额"/, '转换必须提供来源基金的转出份额')
      assert.match(html, /aria-label="转入份额"/)
      assert.match(html, /aria-label="转出金额"/)
      assert.match(html, /aria-label="转入金额"/)
    }
    results.push({ kind, passed: true })
  } catch (error) {
    results.push({ kind, passed: false, message: error.message.split('\n')[0] })
  }
}
console.log(JSON.stringify(results, null, 2))
if (results.some((result) => !result.passed)) process.exitCode = 1
