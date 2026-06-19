import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { getSimulationHistory } from '@/lib/api/simulation'
import { cn } from '@/lib/utils'

interface HistoryProject {
  simulation_id?: string
  project_id?: string
  report_id?: string
  simulation_requirement?: string
  files?: { filename: string }[]
  created_at?: string
  current_round?: number
  total_rounds?: number
}

function formatSimId(id?: string) {
  if (!id) return 'SIM_UNKNOWN'
  return `SIM_${id.replace('sim_', '').slice(0, 6).toUpperCase()}`
}
function fileExt(name?: string) {
  return name?.split('.').pop()?.toUpperCase() || 'FILE'
}
function truncate(text: string | undefined, max: number) {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}
function formatDateTime(s?: string) {
  if (!s) return ''
  try {
    const d = new Date(s)
    return `${d.toISOString().slice(0, 10)} ${d.getHours().toString().padStart(2, '0')}:${d
      .getMinutes()
      .toString()
      .padStart(2, '0')}`
  } catch {
    return ''
  }
}

interface HistoryDatabaseProps {
  /** 历史项目加载完成后回调（用于首页决定是否显示"滚动到历史"按钮）。 */
  onHasProjects?: (hasProjects: boolean) => void
}

/** 首页历史库：展示历史模拟项目卡片，点击查看详情并回放到对应步骤。 */
export function HistoryDatabase({ onHasProjects }: HistoryDatabaseProps = {}) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<HistoryProject[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<HistoryProject | null>(null)
  // 进入视口前卡片处于堆叠/淡入态，进入后展开为网格
  const [revealed, setRevealed] = useState(false)
  const loadedRef = useRef(false)
  const sectionRef = useRef<HTMLElement | null>(null)

  const load = useCallback(async () => {
    try {
      setLoading(true)
      const res = await getSimulationHistory(20)
      const list = res.success ? res.data || [] : []
      setProjects(list)
      onHasProjects?.(list.length > 0)
    } catch (err) {
      console.error('加载历史项目失败:', err)
      setProjects([])
      onHasProjects?.(false)
    } finally {
      setLoading(false)
    }
  }, [onHasProjects])

  useEffect(() => {
    if (loadedRef.current) return
    loadedRef.current = true
    void load()
  }, [load])

  // 进入视口时触发展开动画（一次性，避免来回滚动反复抖动）
  useEffect(() => {
    if (loading || projects.length === 0) return
    const el = sectionRef.current
    if (!el) return

    // 尊重用户的“减少动效”偏好：直接展开，不做过渡
    const reduceMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      setRevealed(true)
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setRevealed(true)
            observer.disconnect()
          }
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -80px 0px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [loading, projects.length])

  const rounds = (p: HistoryProject) => {
    const total = p.total_rounds || 0
    if (total === 0) return t('history.notStarted')
    return t('history.roundsProgress', { current: p.current_round || 0, total })
  }

  if (loading) {
    return (
      <div className="text-muted-foreground flex items-center justify-center gap-2 py-12 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        {t('history.loadingText')}
      </div>
    )
  }

  if (projects.length === 0) return null

  return (
    <section id="history-section" ref={sectionRef} className="mt-12 scroll-mt-6">
      <div className="mb-4 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-muted-foreground text-xs font-semibold uppercase tracking-wider">
          {t('history.title')}
        </span>
        <Separator className="flex-1" />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {projects.map((p, index) => {
          // 折叠态：以网格中心为基准做扇形堆叠（左右偏移 + 旋转 + 缩放 + 下沉）
          const centerIndex = (projects.length - 1) / 2
          const offset = index - centerIndex
          const stackStyle: React.CSSProperties = {
            transform: `translate3d(${offset * 22}px, ${24 + Math.abs(offset) * 6}px, 0) rotate(${offset * 2.5}deg) scale(0.92)`,
            opacity: 0,
          }
          const gridStyle: React.CSSProperties = {
            transform: 'translate3d(0, 0, 0) rotate(0deg) scale(1)',
            opacity: 1,
          }
          // 进场轻微错峰，营造“逐张归位”的观感；上限避免后排卡片等待过久
          const delay = revealed ? `${Math.min(index, 11) * 45}ms` : '0ms'

          return (
            <button
              key={p.simulation_id}
              onClick={() => setSelected(p)}
              style={{
                ...(revealed ? gridStyle : stackStyle),
                transitionDelay: delay,
                willChange: 'transform, opacity',
              }}
              className={cn(
                'bg-card group relative isolate overflow-hidden rounded-lg border p-4 text-left',
                'transition-[transform,opacity,box-shadow,border-color] duration-700 ease-[cubic-bezier(0.23,1,0.32,1)]',
                'hover:border-brand hover:-translate-y-1 hover:shadow-lg',
                'motion-reduce:transition-none',
              )}
            >
              {/* 取景框风格角标 */}
              <span className="border-foreground/40 pointer-events-none absolute left-1.5 top-1.5 h-2 w-2 border-l-[1.5px] border-t-[1.5px] opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

              <div className="mb-2 flex items-center justify-between">
                <span className="text-muted-foreground group-hover:text-brand font-mono text-xs font-bold transition-colors">
                  {formatSimId(p.simulation_id)}
                </span>
                <div className="flex gap-1 text-xs">
                  <span className={p.project_id ? 'text-brand' : 'text-muted-foreground/40'}>
                    ◇
                  </span>
                  <span className="text-brand">◈</span>
                  <span className={p.report_id ? 'text-brand' : 'text-muted-foreground/40'}>◆</span>
                </div>
              </div>

              <h3 className="group-hover:text-brand mb-1 truncate text-sm font-semibold transition-colors">
                {truncate(p.simulation_requirement, 20) || t('history.untitledSimulation')}
              </h3>
              <p className="text-muted-foreground mb-3 line-clamp-2 text-xs">
                {truncate(p.simulation_requirement, 55)}
              </p>

              {/* 文件预览 */}
              {p.files && p.files.length > 0 ? (
                <div className="mb-3 flex flex-wrap gap-1">
                  {p.files.slice(0, 3).map((f, i) => (
                    <Badge key={i} variant="secondary" className="font-mono text-[10px]">
                      {fileExt(f.filename)}
                    </Badge>
                  ))}
                  {p.files.length > 3 && (
                    <span className="text-muted-foreground self-center font-mono text-[10px]">
                      {t('history.moreFiles', { count: p.files.length - 3 })}
                    </span>
                  )}
                </div>
              ) : (
                <div className="text-muted-foreground/60 mb-3 font-mono text-[10px]">
                  {t('history.noFiles')}
                </div>
              )}

              <div className="text-muted-foreground flex items-center justify-between border-t pt-2 text-[10px]">
                <span className="font-mono">{formatDateTime(p.created_at)}</span>
                <span className="font-mono">{rounds(p)}</span>
              </div>

              {/* 底部强调线（hover 时展开） */}
              <span className="bg-brand absolute bottom-0 left-0 h-0.5 w-0 transition-all duration-500 ease-[cubic-bezier(0.23,1,0.32,1)] group-hover:w-full" />
            </button>
          )
        })}
      </div>

      {/* 详情模态 */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          {selected && (
            <>
              <DialogHeader>
                <DialogTitle className="font-mono text-sm">
                  {formatSimId(selected.simulation_id)}
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <div className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase">
                    {t('history.simRequirement')}
                  </div>
                  <p className="text-sm">{selected.simulation_requirement || t('common.none')}</p>
                </div>
                {!!selected.files?.length && (
                  <div>
                    <div className="text-muted-foreground mb-1 text-[10px] font-semibold uppercase">
                      {t('history.relatedFiles')}
                    </div>
                    <div className="space-y-1">
                      {selected.files.map((f, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm">
                          <Badge variant="secondary" className="text-[10px]">
                            {fileExt(f.filename)}
                          </Badge>
                          <span className="truncate">{f.filename}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <div className="grid grid-cols-3 gap-2 border-t pt-4">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!selected.project_id}
                  onClick={() => navigate(`/process/${selected.project_id}`)}
                >
                  {t('history.step1Button')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!selected.simulation_id}
                  onClick={() => navigate(`/simulation/${selected.simulation_id}`)}
                >
                  {t('history.step2Button')}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!selected.report_id}
                  onClick={() => navigate(`/report/${selected.report_id}`)}
                >
                  {t('history.step4Button')}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  )
}
