import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { StepCard } from '@/components/StepCard'
import { Button } from '@/components/ui/button'
import { createSimulation, listSimulations } from '@/lib/api/simulation'
import type { ProjectData } from '@/lib/process-types'

interface Props {
  phase: number
  projectData: ProjectData | null
}

/** 步骤 03：构建完成（创建模拟并进入环境搭建）。 */
export function CompleteCard({ phase, projectData }: Props) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [creating, setCreating] = useState(false)
  const [rebuilding, setRebuilding] = useState(false)
  const busy = creating || rebuilding

  /**
   * 进入环境搭建 / 重建环境。
   * forceNew=false：优先复用项目下已有模拟（续做），无则新建。
   * forceNew=true：跳过复用，强制基于当前图谱新建一个全新环境。
   */
  const handleEnter = async (forceNew: boolean) => {
    if (!projectData?.project_id || !projectData?.graph_id || busy) return
    const setBusy = forceNew ? setRebuilding : setCreating
    setBusy(true)
    try {
      // 复用：若该项目已创建过模拟，直接进入（仅展示/续做），不重复新建。
      // 优先已生成配置（可用）的那个，避免落到半成品的 preparing 副本；否则取最新。
      if (!forceNew) {
        const existing = await listSimulations(projectData.project_id)
        if (existing.success && existing.data && existing.data.length > 0) {
          const sims = existing.data // 后端按 created_at 倒序
          const target = sims.find((s) => s.config_generated || s.status === 'ready') || sims[0]
          if (target.simulation_id) {
            navigate(`/simulation/${target.simulation_id}`)
            return
          }
        }
      }
      const res = await createSimulation({
        project_id: projectData.project_id,
        graph_id: projectData.graph_id,
        enable_twitter: true,
        enable_reddit: true,
      })
      if (res.success && res.data?.simulation_id) {
        navigate(`/simulation/${res.data.simulation_id}`)
      } else {
        toast.error(
          t('step1.createSimulationFailed', { error: res.error || t('common.unknownError') }),
        )
      }
    } catch (err) {
      toast.error(t('step1.createSimulationException', { error: (err as Error).message }))
    } finally {
      setBusy(false)
    }
  }

  const handleRebuild = () => {
    if (busy) return
    if (!window.confirm(t('step1.rebuildEnvConfirm'))) return
    void handleEnter(true)
  }

  return (
    <StepCard
      num="03"
      title={t('step1.buildComplete')}
      status={phase >= 2 ? 'processing' : 'pending'}
      statusText={phase >= 2 ? t('step1.inProgress') : undefined}
      active={phase >= 2}
      apiNote="POST /api/simulation/create"
      description={t('step1.buildCompleteDesc')}
    >
      <Button className="w-full" onClick={() => handleEnter(false)} disabled={phase < 2 || busy}>
        {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {creating ? t('step1.creating') : `${t('step1.enterEnvSetup')} ➝`}
      </Button>

      {/* 重建环境：丢弃已有模拟，基于当前图谱强制新建一个全新环境 */}
      <Button
        variant="outline"
        size="sm"
        onClick={handleRebuild}
        disabled={phase < 2 || busy}
        className="mt-3 w-full gap-1.5"
        title={t('step1.rebuildEnvHint')}
      >
        <RefreshCw className={`h-3.5 w-3.5 ${rebuilding ? 'animate-spin' : ''}`} />
        {t('step1.rebuildEnv')}
      </Button>
    </StepCard>
  )
}
