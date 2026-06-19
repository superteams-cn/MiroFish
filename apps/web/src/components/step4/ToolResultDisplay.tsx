import { useLayoutEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import {
  parseInsightForge,
  parseInterview,
  parsePanorama,
  parseQuickSearch,
  toResultText,
} from '@/lib/step4-parsers'
import { InsightDisplay } from './InsightDisplay'
import { InterviewDisplay } from './InterviewDisplay'
import { PanoramaDisplay } from './PanoramaDisplay'
import { QuickSearchDisplay } from './QuickSearchDisplay'

const STRUCTURED_TOOLS = new Set([
  'insight_forge',
  'panorama_search',
  'interview_agents',
  'quick_search',
])

function formatResultSize(length?: number) {
  if (!length) return ''
  if (length < 1000) return `${length} chars`
  return `${(length / 1000).toFixed(1)}k chars`
}

/** 工具结果分流渲染：按工具类型走专用结构化组件，未知工具/解析失败兜底为原始文本(JSON)。 */
export function ToolResultDisplay({
  toolName,
  result,
  resultLength,
}: {
  toolName?: string
  result: unknown
  resultLength?: number
}) {
  const { t } = useTranslation()
  const [raw, setRaw] = useState(false)
  const text = toResultText(result)
  const structured = !!toolName && STRUCTURED_TOOLS.has(toolName)

  // 切换 Raw/Structured 时保持切换按钮在视口中的位置（避免内容高度突变导致跳动）。
  const btnRef = useRef<HTMLButtonElement>(null)
  const topBefore = useRef<number | null>(null)
  const toggle = () => {
    topBefore.current = btnRef.current?.getBoundingClientRect().top ?? null
    setRaw((v) => !v)
  }
  useLayoutEffect(() => {
    if (topBefore.current == null || !btnRef.current) return
    const scroller = btnRef.current.closest('.overflow-y-auto') as HTMLElement | null
    if (scroller) {
      const after = btnRef.current.getBoundingClientRect().top
      scroller.scrollTop += after - topBefore.current
    }
    topBefore.current = null
  }, [raw])

  const rawBlock = (
    <pre className="bg-muted mt-1.5 max-h-60 overflow-auto whitespace-pre-wrap rounded p-2 text-[10px] leading-relaxed">
      {text}
    </pre>
  )

  // 非结构化工具：元信息头 + 截断预览（300 字），可切到完整原始输出。
  if (!structured) {
    const truncated = text.length > 300 ? text.slice(0, 300) + '...' : text
    const canToggle = text.length > 300
    return (
      <div>
        <div className="text-muted-foreground mt-1.5 flex items-center justify-between text-[10px]">
          {toolName && <span className="font-medium">{toolName}</span>}
          {resultLength != null && <span>{formatResultSize(resultLength)}</span>}
        </div>
        <pre className="bg-muted mt-1 max-h-60 overflow-auto whitespace-pre-wrap rounded p-2 text-[10px] leading-relaxed">
          {raw ? text : truncated}
        </pre>
        {canToggle && (
          <Button
            ref={btnRef}
            variant="link"
            size="sm"
            className="text-brand mt-1 h-auto p-0 text-[10px]"
            onClick={toggle}
          >
            {raw ? t('step4.structuredView') : t('step4.rawOutput')}
          </Button>
        )}
      </div>
    )
  }

  return (
    <div>
      {raw ? (
        rawBlock
      ) : (
        <div className="bg-card mt-1.5 rounded-md border p-2.5">
          {toolName === 'insight_forge' && (
            <InsightDisplay result={parseInsightForge(text)} resultLength={resultLength} />
          )}
          {toolName === 'panorama_search' && (
            <PanoramaDisplay result={parsePanorama(text)} resultLength={resultLength} />
          )}
          {toolName === 'interview_agents' && (
            <InterviewDisplay result={parseInterview(text)} resultLength={resultLength} />
          )}
          {toolName === 'quick_search' && (
            <QuickSearchDisplay result={parseQuickSearch(text)} resultLength={resultLength} />
          )}
        </div>
      )}
      <Button
        ref={btnRef}
        variant="link"
        size="sm"
        className="text-brand mt-1 h-auto p-0 text-[10px]"
        onClick={toggle}
      >
        {raw ? t('step4.structuredView') : t('step4.rawOutput')}
      </Button>
    </div>
  )
}
