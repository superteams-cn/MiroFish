/**
 * 推演旅程导航状态：把整条旅程的关键 ID（项目 / 模拟 / 报告）与「已到达的最远阶段」
 * 持久化到 sessionStorage，使顶部进度条上任何「已到达过」的阶段都能点击跳转——
 * 即使当前已退回到更早的阶段。每个页面挂载时调用 recordStage 记录自身。
 *
 * 5 阶段 ↔ 路由：
 *  1 读懂你的世界  /process/:projectId
 *  2 召集虚拟的人  /simulation/:simulationId
 *  3 让他们演一遍  /simulation/:simulationId/start
 *  4 给你结论      /report/:reportId
 *  5 深入追问      /interaction/:reportId
 */

const KEY = 'sf_journey'

export interface JourneyState {
  projectId?: string
  simulationId?: string
  reportId?: string
  /** 已到达的最远阶段（1-5） */
  reachedStep: number
}

export interface JourneyIds {
  projectId?: string
  simulationId?: string
  reportId?: string
}

export function readJourney(): JourneyState {
  try {
    const raw = sessionStorage.getItem(KEY)
    if (raw) return JSON.parse(raw) as JourneyState
  } catch {
    // 解析失败 → 回退到空旅程
  }
  return { reachedStep: 0 }
}

function writeJourney(j: JourneyState) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(j))
  } catch {
    // 写入失败（隐私模式等）静默忽略，仅影响跨页跳转便利性
  }
}

/**
 * 记录当前页面所处阶段及已知 ID。
 * 若传入的 projectId 与已存不同 → 视为开启了新的推演，重置整条旅程。
 */
export function recordStage(step: number, ids: JourneyIds): JourneyState {
  let j = readJourney()
  if (ids.projectId && j.projectId && ids.projectId !== j.projectId) {
    j = { reachedStep: 0 }
  }
  j = {
    ...j,
    ...Object.fromEntries(Object.entries(ids).filter(([, v]) => v)),
    reachedStep: Math.max(j.reachedStep || 0, step),
  }
  writeJourney(j)
  return j
}

/** 某阶段（1-5）当前是否有可跳转的 URL（取决于已记录的 ID）。 */
export function stageUrl(step: number, j: JourneyState): string | null {
  switch (step) {
    case 1:
      return j.projectId ? `/process/${j.projectId}` : null
    case 2:
      return j.simulationId ? `/simulation/${j.simulationId}` : null
    case 3:
      return j.simulationId ? `/simulation/${j.simulationId}/start` : null
    case 4:
      return j.reportId ? `/report/${j.reportId}` : null
    case 5:
      return j.reportId ? `/interaction/${j.reportId}` : null
    default:
      return null
  }
}
