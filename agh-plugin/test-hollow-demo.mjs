import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'

const { mechanicalTools } = await import('./index.mjs')
const caseFile = JSON.parse(await readFile(new URL('../cases/hollow_demo_cases.json', import.meta.url), 'utf8'))
const constraints = Object.values(caseFile)[1]
const cases = Object.values(caseFile)[2]

function getHollowTool() {
  let tool
  mechanicalTools.apply({
    extension: () => ({
      registerTool(candidate) {
        if (candidate.name === 'calculate_hollow_cantilever') tool = candidate
      },
    }),
  })
  assert.ok(tool, 'calculate_hollow_cantilever 未注册')
  return tool
}

test('空心案例通过插件封装返回预期状态', async () => {
  const tool = getHollowTool()
  const feasible = cases.find((item) => item.id === 'hollow-feasible')
  const result = await tool.execute({ ...feasible['输入'], ...constraints })
  assert.equal(result.structured.ok, true)
  assert.equal(result.structured.status, 'feasible')
  assert.equal(result.structured.stability_screening.status, 'passed')
})

test('空心初始失败案例返回失败约束而不是异常', async () => {
  const tool = getHollowTool()
  const initialFailure = cases.find((item) => item.id === 'hollow-initial-failure')
  const result = await tool.execute({ ...initialFailure['输入'], ...constraints })
  assert.equal(result.structured.ok, true)
  assert.equal(result.structured.status, 'constraint_failed')
  assert.deepEqual(result.structured.failed_constraints, ['deflection', 'safety_factor'])
})

test('空心非法几何案例返回结构化输入错误', async () => {
  const tool = getHollowTool()
  const invalid = cases.find((item) => item.id === 'hollow-invalid-geometry')
  const result = await tool.execute({ ...invalid['输入'], ...constraints })
  assert.equal(result.structured.ok, false)
  assert.equal(result.structured.error_code, 'INVALID_GEOMETRY')
})

test('六种材料均执行局部屈曲筛查', async () => {
  const tool = getHollowTool()
  const materialCase = cases.find((item) => item.id === 'hollow-material-screening')
  const rows = []
  for (const materialId of materialCase['输入'].material_ids) {
    const { material_ids: ignored, ...base } = materialCase['输入']
    const result = await tool.execute({ ...base, ...constraints, material_id: materialId })
    assert.equal(result.structured.ok, true)
    rows.push(result.structured.stability_screening.status)
  }
  assert.deepEqual(rows, ['passed', 'passed', 'passed', 'passed', 'passed', 'passed'])
})
