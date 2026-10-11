import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import process from 'node:process'

const Kind = Symbol.for('TypeBox.Kind')
const materialIds = [
  'steel_s235',
  'aluminum_6061_t6',
  'steel_s355',
  'stainless_steel_304',
  'aluminum_7075_t6',
  'titanium_ti6al4v',
]
const parameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
  },
  required: ['load_n', 'length_mm', 'width_mm', 'height_mm', 'material_id'],
  additionalProperties: false,
}

const hollowParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    wall_thickness_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_corner_radius_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_local_buckling_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
  },
  required: ['load_n', 'length_mm', 'outer_width_mm', 'outer_height_mm', 'wall_thickness_mm', 'outer_corner_radius_mm', 'material_id'],
  additionalProperties: false,
}

const searchParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    width_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    height_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_candidates: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0, maximum: 1000 },
  },
  required: ['load_n', 'length_mm', 'material_id', 'width_options_mm', 'height_options_mm'],
  additionalProperties: false,
}

const hollowSearchParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    outer_width_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    outer_height_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    wall_thickness_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    outer_corner_radius_options_mm: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 }, minItems: 1, maxItems: 100 },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_local_buckling_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_candidates: { [Kind]: 'Integer', type: 'integer', minimum: 1, maximum: 1000 },
  },
  required: ['load_n', 'length_mm', 'material_id', 'outer_width_options_mm', 'outer_height_options_mm', 'wall_thickness_options_mm', 'outer_corner_radius_options_mm'],
  additionalProperties: false,
}

const sensitivityParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    perturbation_percent: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0, maximum: 20 },
  },
  required: ['load_n', 'length_mm', 'width_mm', 'height_mm', 'material_id'],
  additionalProperties: false,
}

const hollowSensitivityParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    wall_thickness_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_corner_radius_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    perturbation_percent: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0, maximum: 20 },
    min_local_buckling_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
  },
  required: ['load_n', 'length_mm', 'outer_width_mm', 'outer_height_mm', 'wall_thickness_mm', 'outer_corner_radius_mm', 'material_id'],
  additionalProperties: false,
}

const toleranceParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    length_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    width_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    height_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    load_tolerance_percent: { [Kind]: 'Number', type: 'number', minimum: 0, maximum: 20 },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
  },
  required: ['load_n', 'length_mm', 'width_mm', 'height_mm', 'material_id'],
  additionalProperties: false,
}

const hollowToleranceParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    load_n: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    length_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_width_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_height_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    wall_thickness_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    outer_corner_radius_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    material_id: { [Kind]: 'String', type: 'string', enum: materialIds },
    length_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    outer_width_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    outer_height_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    wall_thickness_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    outer_corner_radius_tolerance_mm: { [Kind]: 'Number', type: 'number', minimum: 0 },
    load_tolerance_percent: { [Kind]: 'Number', type: 'number', minimum: 0, maximum: 20 },
    max_deflection_mm: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_safety_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    max_mass_kg: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
    min_local_buckling_factor: { [Kind]: 'Number', type: 'number', exclusiveMinimum: 0 },
  },
  required: ['load_n', 'length_mm', 'outer_width_mm', 'outer_height_mm', 'wall_thickness_mm', 'outer_corner_radius_mm', 'material_id'],
  additionalProperties: false,
}

const dossierParameters = {
  [Kind]: 'Object',
  type: 'object',
  properties: {
    project_name: { [Kind]: 'String', type: 'string', minLength: 1, maxLength: 200 },
    task_summary: { [Kind]: 'String', type: 'string', minLength: 1, maxLength: 4000 },
    final_status: { [Kind]: 'String', type: 'string', minLength: 1, maxLength: 100 },
    format: { [Kind]: 'String', type: 'string', enum: ['markdown', 'html'] },
    // Prefer structured values so AGH does not need to quote and re-parse a
    // long JSON document inside a string. The *_json fields remain for old
    // sessions and are normalized by the deterministic Python tool.
    calculation_result: { [Kind]: 'Object', type: 'object', additionalProperties: true },
    search_result: { [Kind]: 'Object', type: 'object', additionalProperties: true },
    sensitivity_result: { [Kind]: 'Object', type: 'object', additionalProperties: true },
    tolerance_result: { [Kind]: 'Object', type: 'object', additionalProperties: true },
    public_reference_result: { [Kind]: 'Object', type: 'object', additionalProperties: true },
    replanning_trace: { [Kind]: 'Array', type: 'array', items: { [Kind]: 'Object', type: 'object', additionalProperties: true } },
    calculation_result_json: { [Kind]: 'String', type: 'string', minLength: 2, maxLength: 200000 },
    search_result_json: { [Kind]: 'String', type: 'string', maxLength: 200000 },
    sensitivity_result_json: { [Kind]: 'String', type: 'string', maxLength: 200000 },
    tolerance_result_json: { [Kind]: 'String', type: 'string', maxLength: 200000 },
    public_reference_result_json: { [Kind]: 'String', type: 'string', maxLength: 200000 },
    replanning_trace_json: { [Kind]: 'String', type: 'string', maxLength: 200000 },
    evidence_note: { [Kind]: 'String', type: 'string', maxLength: 4000 },
  },
  required: ['project_name', 'task_summary', 'final_status'],
  additionalProperties: false,
}

const meta = {
  isReadOnly: true,
  isDestructive: false,
  isConcurrencySafe: true,
  isOpenWorld: false,
  replay: 'safe',
  costHint: undefined,
  deferLoading: false,
  requiresApproval: 'never',
}

const pluginDirectory = dirname(fileURLToPath(import.meta.url))
const configuredRoot = process.env.MECHANICAL_AGENT_ROOT
  ? resolve(process.env.MECHANICAL_AGENT_ROOT)
  : null
const candidateRoots = [
  configuredRoot,
  pluginDirectory,
  resolve(pluginDirectory, '..'),
].filter(Boolean)
const projectRoot = candidateRoots.find((root) => (
  existsSync(resolve(root, 'tools', 'cantilever_calculator.py'))
)) || configuredRoot || pluginDirectory
const toolDirectory = resolve(projectRoot, 'tools')
const bundledPythonExecutable = process.platform === 'win32'
  ? resolve(projectRoot, '.venv', 'Scripts', 'python.exe')
  : resolve(projectRoot, '.venv', 'bin', 'python')
const pythonExecutable = process.env.PYTHON_EXEC || (
  existsSync(bundledPythonExecutable)
    ? bundledPythonExecutable
    : (process.platform === 'win32' ? 'python.exe' : 'python')
)

const toolPaths = {
  calculate_cantilever: resolve(toolDirectory, 'cantilever_calculator.py'),
  calculate_hollow_cantilever: resolve(toolDirectory, 'hollow_cantilever_calculator.py'),
  search_hollow_design_candidates: resolve(toolDirectory, 'hollow_design_search.py'),
  search_design_candidates: resolve(toolDirectory, 'design_search.py'),
  analyze_design_sensitivity: resolve(toolDirectory, 'design_sensitivity.py'),
  analyze_hollow_design_sensitivity: resolve(toolDirectory, 'hollow_design_sensitivity.py'),
  verify_manufacturing_tolerance: resolve(toolDirectory, 'manufacturing_tolerance.py'),
  verify_hollow_manufacturing_tolerance: resolve(toolDirectory, 'hollow_manufacturing_tolerance.py'),
  generate_design_dossier: resolve(toolDirectory, 'design_dossier.py'),
}
const pythonToolTimeoutMs = Number.parseInt(process.env.PYTHON_TOOL_TIMEOUT_MS || '10000', 10)

function executePythonTool(scriptPath, input) {
  return new Promise((settle) => {
    let completed = false
    let timedOut = false
    let stdinError = null
    let stdout = ''
    let stderr = ''
    let child
    let timer

    const finish = (result) => {
      if (completed) return
      completed = true
      clearTimeout(timer)
      settle(result)
    }

    try {
      child = spawn(pythonExecutable, ['-B', scriptPath], {
        cwd: projectRoot,
        env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
        windowsHide: true,
      })
    } catch (error) {
      finish({ ok: false, error_code: 'PYTHON_EXECUTION_ERROR', message: error.message })
      return
    }

    timer = setTimeout(() => {
      timedOut = true
      child.kill()
    }, Number.isFinite(pythonToolTimeoutMs) && pythonToolTimeoutMs > 0 ? pythonToolTimeoutMs : 10000)

    child.stdout.on('data', (chunk) => { stdout += chunk })
    child.stderr.on('data', (chunk) => { stderr += chunk })
    child.on('error', (error) => {
      finish({ ok: false, error_code: 'PYTHON_EXECUTION_ERROR', message: error.message })
    })
    child.stdin.on('error', (error) => { stdinError = error })
    child.on('close', (code) => {
      if (timedOut) {
        finish({ ok: false, error_code: 'PYTHON_TIMEOUT', message: 'Python tool exceeded the 10 second timeout.' })
        return
      }
      if (!stdout.trim()) {
        finish({
          ok: false,
          error_code: 'PYTHON_EXECUTION_ERROR',
          message: stdinError?.message || stderr || `Python exited with code ${code}`,
        })
        return
      }
      try {
        finish(JSON.parse(stdout))
      } catch (error) {
        finish({ ok: false, error_code: 'INVALID_TOOL_OUTPUT', message: error.message, raw_output: stdout.slice(0, 2000) })
      }
    })
    child.stdin.end(JSON.stringify(input), (error) => {
      if (error) stdinError = error
    })
  })
}

export const mechanicalTools = {
  inject: ['extension'],
  apply(ctx) {
    const agnes = ctx.extension()
    agnes.registerTool({
      name: 'calculate_cantilever',
      description: '使用团队开发的确定性公式计算矩形截面悬臂支架的应力、挠度、质量和安全系数，并校核约束。',
      parameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.calculate_cantilever, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'calculate_hollow_cantilever',
      description: '使用团队开发的确定性公式计算实际圆角空心矩形截面悬臂支架，并分别执行翼缘和腹板的弹性局部屈曲筛查；结果不等同于完整规范验算。',
      parameters: hollowParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.calculate_hollow_cantilever, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'search_hollow_design_candidates',
      description: '使用团队开发的确定性四维网格搜索枚举圆角空心矩形截面的外宽、外高、壁厚和外圆角；跳过并记录非法几何，同时校核静力和弹性局部屈曲约束。',
      parameters: hollowSearchParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.search_hollow_design_candidates, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'search_design_candidates',
      description: '使用团队开发的确定性网格搜索，遍历矩形截面候选尺寸，筛选并排序满足约束的悬臂支架方案。',
      parameters: searchParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.search_design_candidates, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'analyze_design_sensitivity',
      description: '使用团队开发的确定性中心差分分析，计算载荷、长度、宽度和高度对悬臂支架指标的相对影响。',
      parameters: sensitivityParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.analyze_design_sensitivity, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'analyze_hollow_design_sensitivity',
      description: '使用团队开发的确定性中心差分分析，计算载荷、长度、外宽、外高、壁厚和圆角对空心截面静力与局部屈曲指标的影响。',
      parameters: hollowSensitivityParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.analyze_hollow_design_sensitivity, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'verify_manufacturing_tolerance',
      description: '使用团队开发的确定性边界枚举，验证尺寸公差和载荷波动下悬臂支架是否仍满足约束。',
      parameters: toleranceParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.verify_manufacturing_tolerance, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'verify_hollow_manufacturing_tolerance',
      description: '使用团队开发的确定性六维边界枚举，验证圆角空心矩形截面在尺寸、壁厚、圆角和载荷公差下的静力与局部屈曲稳健性。',
      parameters: hollowToleranceParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.verify_hollow_manufacturing_tolerance, input)
        return {
          content: [{ type: 'text', text: JSON.stringify(structured) }],
          structured,
        }
      },
    })
    agnes.registerTool({
      name: 'generate_design_dossier',
      description: '使用团队开发的确定性模板，根据已返回的实心或圆角空心结构化计算、搜索、敏感性、公差和重规划结果生成工程报告内容。请优先传入真正的结构化对象字段 calculation_result、search_result、sensitivity_result、tolerance_result 和数组字段 replanning_trace；不要把长结果转成字符串。默认返回Markdown；用户明确要求HTML时返回HTML。不会补造缺失数据，不调用模型，也不直接写入文件。',
      parameters: dossierParameters,
      meta,
      async execute(input) {
        const structured = await executePythonTool(toolPaths.generate_design_dossier, input)
        return {
          content: [{ type: 'text', text: structured.content || JSON.stringify(structured) }],
          structured,
        }
      },
    })
  },
}
