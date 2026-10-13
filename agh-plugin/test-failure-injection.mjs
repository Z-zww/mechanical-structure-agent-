import assert from 'node:assert/strict'
import { cp, mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { test } from 'node:test'

const pluginSource = dirname(fileURLToPath(import.meta.url))
const bundledPython = process.platform === 'win32'
  ? join(pluginSource, '..', '.venv', 'Scripts', 'python.exe')
  : join(pluginSource, '..', '.venv', 'bin', 'python')
const pythonExecutable = process.env.PYTHON_EXEC || (
  existsSync(bundledPython)
    ? bundledPython
    : (process.platform === 'win32' ? 'python.exe' : 'python')
)

async function createScenario(source, layout = 'sibling') {
  const root = await mkdtemp(join(tmpdir(), 'mechanical-agent-plugin-test-'))
  const pluginDirectory = join(root, 'agh-plugin')
  const toolsDirectory = layout === 'package' ? join(pluginDirectory, 'tools') : join(root, 'tools')
  await mkdir(pluginDirectory, { recursive: true })
  await mkdir(toolsDirectory, { recursive: true })
  await cp(join(pluginSource, 'index.mjs'), join(pluginDirectory, 'index.mjs'))
  if (source !== null) {
    await writeFile(join(toolsDirectory, 'cantilever_calculator.py'), source, 'utf8')
  }
  return { root, pluginDirectory }
}

async function invokeCalculator(scenario, executable = pythonExecutable) {
  const oldPython = process.env.PYTHON_EXEC
  const oldTimeout = process.env.PYTHON_TOOL_TIMEOUT_MS
  process.env.PYTHON_EXEC = executable
  process.env.PYTHON_TOOL_TIMEOUT_MS = '1000'
  try {
    const moduleUrl = `${pathToFileURL(join(scenario.pluginDirectory, 'index.mjs')).href}?case=${Date.now()}-${Math.random()}`
    const { mechanicalTools } = await import(moduleUrl)
    let registeredTool
    mechanicalTools.apply({ extension: () => ({ registerTool: (tool) => { if (tool.name === 'calculate_cantilever') registeredTool = tool } }) })
    assert.ok(registeredTool, 'calculate_cantilever was not registered')
    return registeredTool.execute({ load_n: 1, length_mm: 1, width_mm: 1, height_mm: 1, material_id: 'steel_s235' })
  } finally {
    if (oldPython === undefined) delete process.env.PYTHON_EXEC
    else process.env.PYTHON_EXEC = oldPython
    if (oldTimeout === undefined) delete process.env.PYTHON_TOOL_TIMEOUT_MS
    else process.env.PYTHON_TOOL_TIMEOUT_MS = oldTimeout
  }
}

async function withScenario(source, callback, executable = pythonExecutable) {
  const scenario = await createScenario(source)
  try {
    await callback(scenario, executable)
  } finally {
    await rm(scenario.root, { recursive: true, force: true })
  }
}

const validJson = 'import sys; sys.stdin.read(); print("{\\"ok\\": true}")'
const emptyOutput = 'import sys; sys.stdin.read()'
const invalidJson = 'import sys; sys.stdin.read(); print("not-json")'
const delayedOutput = 'import sys, time; sys.stdin.read(); time.sleep(2); print("{\\"ok\\": true}")'

test('returns structured success for a valid tool result', async () => {
  await withScenario(validJson, async (scenario) => {
    const result = await invokeCalculator(scenario)
    assert.deepEqual(result.structured, { ok: true })
  })
})

test('resolves tools bundled inside a relocated plugin package', async () => {
  const scenario = await createScenario(validJson, 'package')
  try {
    const result = await invokeCalculator(scenario)
    assert.deepEqual(result.structured, { ok: true })
  } finally {
    await rm(scenario.root, { recursive: true, force: true })
  }
})

test('returns execution error when the script is missing', async () => {
  await withScenario(null, async (scenario) => {
    const result = await invokeCalculator(scenario)
    assert.equal(result.structured.error_code, 'PYTHON_EXECUTION_ERROR')
  })
})

test('returns execution error for an unavailable interpreter', async () => {
  await withScenario(validJson, async (scenario) => {
    const result = await invokeCalculator(scenario, join(scenario.root, 'missing-python.exe'))
    assert.equal(result.structured.error_code, 'PYTHON_EXECUTION_ERROR')
  })
})

test('returns execution error for empty output', async () => {
  await withScenario(emptyOutput, async (scenario) => {
    const result = await invokeCalculator(scenario)
    assert.equal(result.structured.error_code, 'PYTHON_EXECUTION_ERROR')
  })
})

test('returns invalid output for malformed JSON', async () => {
  await withScenario(invalidJson, async (scenario) => {
    const result = await invokeCalculator(scenario)
    assert.equal(result.structured.error_code, 'INVALID_TOOL_OUTPUT')
  })
})

test('returns timeout when the tool exceeds the configured limit', async () => {
  await withScenario(delayedOutput, async (scenario) => {
    const result = await invokeCalculator(scenario)
    assert.equal(result.structured.error_code, 'PYTHON_TIMEOUT')
  })
})
