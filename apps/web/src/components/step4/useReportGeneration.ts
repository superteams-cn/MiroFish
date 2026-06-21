import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  getAgentLog,
  getConsoleLog,
  getReport,
  getReportProgress,
  getReportSections,
} from '@/lib/api/report'
import { usePolling } from '@/hooks/usePolling'
import type { AgentLogEntry, ReportOutline } from '@/lib/step4-types'
import type { WorkflowStatus } from '@/components/WorkflowLayout'

interface Options {
  reportId: string
  addLog: (msg: string) => void
  onUpdateStatus: (s: WorkflowStatus) => void
}

/**
 * 步骤四报告生成的编排逻辑：快照 / Agent 日志 / 控制台 三路轮询 + 章节流式合并。
 *
 * 收拢全部计时器、行号 ref、轮询回调与生命周期副作用；Step4Report 仅消费返回的状态做
 * 渲染，并用 resetView / startPolling / stopPolling 实现「重新生成」。行为与原内联实现一致。
 */
export function useReportGeneration({ reportId, addLog, onUpdateStatus }: Options) {
  const { t } = useTranslation()

  const [agentLogs, setAgentLogs] = useState<AgentLogEntry[]>([])
  const [consoleLogs, setConsoleLogs] = useState<string[]>([])
  const [outline, setOutline] = useState<ReportOutline | null>(null)
  const [currentSectionIndex, setCurrentSectionIndex] = useState<number | null>(null)
  const [generatedSections, setGeneratedSections] = useState<Record<number, string>>({})
  const [isComplete, setIsComplete] = useState(false)

  const agentLine = useRef(0)
  const consoleLine = useRef(0)
  // 三路轮询回调存 ref，供 usePolling 取最新实现（打破定义顺序的循环依赖）
  const fetchSnapshotRef = useRef<() => void | Promise<void>>(() => {})
  const fetchAgentLogRef = useRef<() => void | Promise<void>>(() => {})
  const fetchConsoleLogRef = useRef<() => void | Promise<void>>(() => {})
  const fetchingSnapshot = useRef(false)
  const outlineRef = useRef<ReportOutline | null>(null)

  // 三路轮询：快照 @2500、Agent 日志 @2000、控制台 @1500；start 时各立即拉一次首屏
  const snapshotPoll = usePolling(() => fetchSnapshotRef.current(), 2500, { immediate: true })
  const agentPoll = usePolling(() => fetchAgentLogRef.current(), 2000, { immediate: true })
  const consolePoll = usePolling(() => fetchConsoleLogRef.current(), 1500, { immediate: true })

  const stopPolling = useCallback(() => {
    snapshotPoll.stop()
    agentPoll.stop()
    consolePoll.stop()
  }, [snapshotPoll, agentPoll, consolePoll])

  const mergeSectionContent = useCallback((sectionIndex: number | undefined, content: unknown) => {
    if (!sectionIndex || typeof content !== 'string' || !content.trim()) return
    setGeneratedSections((prev) => {
      if (prev[sectionIndex] === content) return prev
      return { ...prev, [sectionIndex]: content }
    })
  }, [])

  const applyOutline = useCallback((nextOutline: ReportOutline) => {
    outlineRef.current = nextOutline
    setOutline(nextOutline)
  }, [])

  const updateCurrentSectionFromTitle = useCallback((title?: string | null) => {
    if (!title) {
      setCurrentSectionIndex(null)
      return
    }
    const idx = outlineRef.current?.sections?.findIndex((section) => section.title === title) ?? -1
    setCurrentSectionIndex(idx >= 0 ? idx + 1 : null)
  }, [])

  const fetchReportSnapshot = useCallback(async () => {
    if (!reportId || fetchingSnapshot.current) return
    fetchingSnapshot.current = true
    try {
      const [reportRes, sectionsRes, progressRes] = await Promise.allSettled([
        getReport(reportId),
        getReportSections(reportId),
        getReportProgress(reportId),
      ])

      if (reportRes.status === 'fulfilled' && reportRes.value.success && reportRes.value.data) {
        const report = reportRes.value.data
        if (report.outline) applyOutline(report.outline)
        if (report.status === 'completed') {
          setIsComplete(true)
          setCurrentSectionIndex(null)
          onUpdateStatus('completed')
        }
      }

      if (
        sectionsRes.status === 'fulfilled' &&
        sectionsRes.value.success &&
        sectionsRes.value.data
      ) {
        const snapshotSections = sectionsRes.value.data.sections || []
        setGeneratedSections((prev) => {
          const next = { ...prev }
          let changed = false
          snapshotSections.forEach((section) => {
            if (!section.section_index || !section.content) return
            if (next[section.section_index] !== section.content) {
              next[section.section_index] = section.content
              changed = true
            }
          })
          return changed ? next : prev
        })
        if (sectionsRes.value.data.is_complete) {
          setIsComplete(true)
          setCurrentSectionIndex(null)
          onUpdateStatus('completed')
        }
      }

      if (
        progressRes.status === 'fulfilled' &&
        progressRes.value.success &&
        progressRes.value.data
      ) {
        const progress = progressRes.value.data
        if (progress.stage === 'completed' || progress.status === 'completed') {
          setIsComplete(true)
          setCurrentSectionIndex(null)
          onUpdateStatus('completed')
        } else if (progress.current_section) {
          updateCurrentSectionFromTitle(progress.current_section)
        }
      }
    } catch (err) {
      addLog(t('log.loadException', { error: (err as Error).message }))
    } finally {
      fetchingSnapshot.current = false
    }
  }, [addLog, applyOutline, onUpdateStatus, reportId, t, updateCurrentSectionFromTitle])

  const fetchAgentLog = useCallback(async () => {
    if (!reportId) return
    try {
      const res = await getAgentLog(reportId, agentLine.current)
      if (!res.success || !res.data) return
      const newLogs: AgentLogEntry[] = res.data.logs || []
      if (!newLogs.length) return

      setAgentLogs((prev) => [...prev, ...newLogs])
      newLogs.forEach((log) => {
        if (log.action === 'planning_complete' && log.details?.outline) {
          applyOutline(log.details.outline)
        }
        if (log.action === 'section_start') {
          setCurrentSectionIndex(log.section_index ?? null)
        }
        if (log.action === 'section_content') {
          mergeSectionContent(log.section_index, log.details?.content)
        }
        if (log.action === 'section_complete' && log.details?.content && log.section_index) {
          mergeSectionContent(log.section_index, log.details.content)
          setCurrentSectionIndex(null)
        }
        if (log.action === 'report_complete') {
          setIsComplete(true)
          setCurrentSectionIndex(null)
          onUpdateStatus('completed')
          stopPolling()
        }
      })
      agentLine.current = res.data.total_lines ?? res.data.from_line + newLogs.length
    } catch (err) {
      addLog(t('log.fetchAgentLogFailed', { error: (err as Error).message }))
    }
  }, [addLog, applyOutline, mergeSectionContent, onUpdateStatus, reportId, stopPolling, t])

  const fetchConsoleLog = useCallback(async () => {
    if (!reportId) return
    try {
      const res = await getConsoleLog(reportId, consoleLine.current)
      if (!res.success || !res.data) return
      const newLogs: string[] = res.data.logs || []
      if (!newLogs.length) return
      setConsoleLogs((prev) => [...prev, ...newLogs])
      consoleLine.current = res.data.total_lines ?? res.data.from_line + newLogs.length
    } catch (err) {
      addLog(t('log.fetchConsoleLogFailed', { error: (err as Error).message }))
    }
  }, [addLog, reportId, t])

  // 清空展示态与行号、停止轮询（重新生成前的乐观重置）。
  const resetView = useCallback(() => {
    stopPolling()
    setAgentLogs([])
    setConsoleLogs([])
    setOutline(null)
    outlineRef.current = null
    setCurrentSectionIndex(null)
    setGeneratedSections({})
    setIsComplete(false)
    agentLine.current = 0
    consoleLine.current = 0
    fetchingSnapshot.current = false
  }, [stopPolling])

  // 让 usePolling 的稳定回调始终指向最新的 fetch 实现
  fetchSnapshotRef.current = fetchReportSnapshot
  fetchAgentLogRef.current = fetchAgentLog
  fetchConsoleLogRef.current = fetchConsoleLog

  // 拉首屏 + 启动三路轮询（仅在有 reportId 时）。immediate 使 start 即拉一次首屏。
  const startPolling = useCallback(() => {
    if (!reportId) return
    snapshotPoll.start()
    agentPoll.start()
    consolePoll.start()
  }, [snapshotPoll, agentPoll, consolePoll, reportId])

  useEffect(() => {
    resetView()
    if (reportId) {
      addLog(t('log.reportAgentInitialized', { reportId }))
      startPolling()
    }
    return () => stopPolling()
  }, [addLog, reportId, resetView, startPolling, stopPolling, t])

  return {
    agentLogs,
    consoleLogs,
    outline,
    currentSectionIndex,
    generatedSections,
    isComplete,
    resetView,
    startPolling,
    stopPolling,
  }
}
