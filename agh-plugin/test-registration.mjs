import assert from 'node:assert/strict'
import { test } from 'node:test'

const { mechanicalTools } = await import('./index.mjs')

const expectedNames = [
  'calculate_cantilever',
  'calculate_hollow_cantilever',
  'search_hollow_design_candidates',
  'search_design_candidates',
  'analyze_design_sensitivity',
  'analyze_hollow_design_sensitivity',
  'verify_manufacturing_tolerance',
  'verify_hollow_manufacturing_tolerance',
  'generate_design_dossier',
  'fe_beam_cantilever',
]

const solidInput = {
  load_n: 500,
  length_mm: 300,
  width_mm: 40,
  height_mm: 60,
  material_id: 'steel_s235',
}

const hollowInput = {
  load_n: 500,
  length_mm: 300,
  outer_width_mm: 60,
  outer_height_mm: 80,
  wall_thickness_mm: 4,
  outer_corner_radius_mm: 8,
  material_id: 'steel_s235',
}

test('registers all tools exactly once and executes one valid sample per tool', async () => {
  const registered = new Map()
  mechanicalTools.apply({
    extension: () => ({
      registerTool(tool) {
        assert.equal(typeof tool.name, 'string')
        assert.equal(typeof tool.execute, 'function')
        assert.equal(typeof tool.parameters, 'object')
        assert.equal(typeof tool.description, 'string')
        assert.ok(!registered.has(tool.name), `重复注册工具: ${tool.name}`)
        registered.set(tool.name, tool)
      },
    }),
  })

  assert.deepEqual([...registered.keys()], expectedNames)

  const payloads = {
    calculate_cantilever: solidInput,
    calculate_hollow_cantilever: hollowInput,
    search_hollow_design_candidates: {
      ...hollowInput,
      outer_width_options_mm: [55, 60],
      outer_height_options_mm: [75, 80],
      wall_thickness_options_mm: [3, 4],
      outer_corner_radius_options_mm: [6, 8],
      max_deflection_mm: 2,
      min_safety_factor: 2.3,
      max_mass_kg: 20,
      min_local_buckling_factor: 1,
    },
    search_design_candidates: {
      load_n: 500,
      length_mm: 300,
      material_id: 'steel_s235',
      width_options_mm: [40],
      height_options_mm: [60],
      max_deflection_mm: 2,
      min_safety_factor: 2.3,
      max_mass_kg: 20,
    },
    analyze_design_sensitivity: solidInput,
    analyze_hollow_design_sensitivity: hollowInput,
    verify_manufacturing_tolerance: {
      ...solidInput,
      length_tolerance_mm: 0,
      width_tolerance_mm: 0,
      height_tolerance_mm: 0,
      load_tolerance_percent: 0,
      max_deflection_mm: 2,
      min_safety_factor: 2.3,
      max_mass_kg: 20,
    },
    verify_hollow_manufacturing_tolerance: {
      ...hollowInput,
      length_tolerance_mm: 0,
      outer_width_tolerance_mm: 0,
      outer_height_tolerance_mm: 0,
      wall_thickness_tolerance_mm: 0,
      outer_corner_radius_tolerance_mm: 0,
      load_tolerance_percent: 0,
      max_deflection_mm: 2,
      min_safety_factor: 2.3,
      max_mass_kg: 20,
      min_local_buckling_factor: 1,
    },
    generate_design_dossier: {
      project_name: '插件注册测试',
      task_summary: '验证所有注册工具均能返回结构化结果。',
      final_status: 'feasible',
      format: 'html',
      success: true,
      elapsed_ms: 12,
      calculation_result: {
        ok: true,
        status: 'feasible',
        formula_version: 'test',
        section_type: 'solid_rectangular',
        input: solidInput,
        material: { id: 'steel_s235', name_zh: 'S235钢' },
        metrics: {
          max_stress_mpa: 6.25,
          max_deflection_mm: 0.03125,
          mass_kg: 5.652,
          safety_factor: 37.6,
        },
        constraints: {},
        failed_constraints: [],
      },
    },
    fe_beam_cantilever: {
      load_n: 1000,
      length_mm: 500,
      youngs_modulus_gpa: 200,
      width_mm: 40,
      height_mm: 70,
      n_elements: 20,
      yield_strength_mpa: 235,
      max_deflection_mm: 2,
      min_safety_factor: 2.3,
    },
  }

  for (const name of expectedNames) {
    const result = await registered.get(name).execute(payloads[name])
    assert.equal(result?.structured?.ok, true, `${name} 未返回 ok=true: ${JSON.stringify(result)}`)
    assert.ok(Array.isArray(result.content), `${name} 缺少 content 数组`)
    assert.ok(result.content.length > 0, `${name} content 为空`)
  }

  const dossierSchema = registered.get('generate_design_dossier').parameters
  assert.equal(dossierSchema.additionalProperties, true)
  assert.deepEqual(dossierSchema.anyOf, [
    { required: ['calculation_result'] },
    { required: ['calculation_result_json'] },
  ])
  assert.match(
    registered.get('generate_design_dossier').execute
      ? (await registered.get('generate_design_dossier').execute(payloads.generate_design_dossier)).content[0].text
      : '',
    /<!doctype html>/i,
  )

  const longCalculation = {
    ...payloads.generate_design_dossier.calculation_result,
    evidence: Array.from({ length: 500 }, (_, index) => ({
      index,
      note: '中文嵌套工程参考数据'.repeat(6),
      checks: { source: 'structured', passed: true },
    })),
  }
  const longDossier = await registered.get('generate_design_dossier').execute({
    ...payloads.generate_design_dossier,
    project_name: '长中文载荷集成测试',
    calculation_result: longCalculation,
    search_result: { status: 'completed', candidates: Array.from({ length: 100 }, (_, index) => ({ index, feasible: true })) },
    sensitivity_result: { status: 'completed', dominant_parameters: ['高度', '长度'] },
    tolerance_result: { status: 'robust_feasible', cases_evaluated: 16, passed_cases: 16 },
    replanning_trace: [{ step: 1, stage: 'candidate_search', decision: '使用结构化数据复核' }],
  })
  assert.equal(longDossier.structured.ok, true, JSON.stringify(longDossier.structured))
  assert.ok(Buffer.byteLength(JSON.stringify(longCalculation), 'utf8') > 20_000)
  assert.match(longDossier.content[0].text, /长中文载荷集成测试/)

  const fea = (await registered.get('fe_beam_cantilever').execute(payloads.fe_beam_cantilever)).structured
  assert.equal(fea.validation_type, 'beam_element_fea_review')
  assert.equal(fea.status, 'feasible')
  assert.ok(fea.comparison.tip_deflection_mm.relative_error < 1e-8)
  assert.equal(fea.mesh_consistency.length, 4)
})
