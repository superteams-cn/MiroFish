import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
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

  const handleEnter = async () => {
    if (!projectData?.project_id || !projectData?.graph_id) return
    setCreating(true)
    try {
      // 复用：若该项目已创建过模拟，直接进入（仅展示/续做），不重复新建。
      // 优先已生成配置（可用）的那个，避免落到半成品的 preparing 副本；否则取最新。
      const existing = await listSimulations(projectData.project_id)
      if (existing.success && existing.data && existing.data.length > 0) {
        const sims = existing.data // 后端按 created_at 倒序
        const target = sims.find((s) => s.config_generated || s.status === 'ready') || sims[0]
        if (target.simulation_id) {
          navigate(`/simulation/${target.simulation_id}`)
          return
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
      setCreating(false)
    }
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
      <Button className="w-full" onClick={handleEnter} disabled={phase < 2 || creating}>
        {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
        {creating ? t('step1.creating') : `${t('step1.enterEnvSetup')} ➝`}
      </Button>
    </StepCard>
  )
}
