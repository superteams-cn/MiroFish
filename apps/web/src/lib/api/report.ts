import { http, requestWithRetry } from './client'
import type {
  AgentLogData,
  ApiEnvelope,
  ChatData,
  ConsoleLogData,
  GenerateReportData,
  ReportData,
  TaskData,
} from './types'

/** 开始报告生成。data: { simulation_id, force_regenerate? } */
export const generateReport = (
  data: Record<string, unknown>,
): Promise<ApiEnvelope<GenerateReportData>> =>
  requestWithRetry(() => http.post<GenerateReportData>('/api/report/generate', data), 3, 1000)

/** 获取报告生成状态。 */
export const getReportStatus = (reportId: string): Promise<ApiEnvelope<TaskData>> =>
  http.get<TaskData>('/api/report/generate/status', { params: { report_id: reportId } })

/** 获取 Agent 日志（增量）。 */
export const getAgentLog = (reportId: string, fromLine = 0): Promise<ApiEnvelope<AgentLogData>> =>
  http.get<AgentLogData>(`/api/report/${reportId}/agent-log`, { params: { from_line: fromLine } })

/** 获取控制台日志（增量）。 */
export const getConsoleLog = (
  reportId: string,
  fromLine = 0,
): Promise<ApiEnvelope<ConsoleLogData>> =>
  http.get<ConsoleLogData>(`/api/report/${reportId}/console-log`, {
    params: { from_line: fromLine },
  })

/** 获取报告详情。 */
export const getReport = (reportId: string): Promise<ApiEnvelope<ReportData>> =>
  http.get<ReportData>(`/api/report/${reportId}`)

/** 与 Report Agent 对话。data: { simulation_id, message, chat_history? } */
export const chatWithReport = (data: Record<string, unknown>): Promise<ApiEnvelope<ChatData>> =>
  requestWithRetry(() => http.post<ChatData>('/api/report/chat', data), 3, 1000)
