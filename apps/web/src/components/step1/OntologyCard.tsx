import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'

import { StepCard } from '@/components/StepCard'
import { OntologyDetailOverlay, type SelectedOntologyItem } from './OntologyDetailOverlay'
import { cn } from '@/lib/utils'
import type { OntologyItem, OntologyProgress, ProjectData } from '@/lib/process-types'

interface Props {
  phase: number
  projectData: ProjectData | null
  ontologyProgress: OntologyProgress | null
}

/** 步骤 01：本体生成（实体/关系类型标签 + 详情浮层）。 */
export function OntologyCard({ phase, projectData, ontologyProgress }: Props) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<SelectedOntologyItem>(null)

  const resolveEntityName = (schemaName: string) =>
    projectData?.ontology?.entity_types?.find((e) => e.name === schemaName)?.name || schemaName

  const status = phase > 0 ? 'completed' : phase === 0 ? 'processing' : 'pending'
  const statusText =
    phase > 0
      ? t('step1.ontologyCompleted')
      : phase === 0
        ? t('step1.ontologyGenerating')
        : t('step1.ontologyPending')

  const tagList = (items: OntologyItem[] | undefined, type: 'entity' | 'relation', label: string) =>
    items && (
      <div className={cn('mt-3 transition', selected && 'pointer-events-none opacity-30')}>
        <span className="mb-2 block text-[10px] font-semibold text-muted-foreground">{label}</span>
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span
              key={item.name}
              onClick={() => setSelected({ ...item, itemType: type })}
              className="cursor-pointer rounded border bg-muted px-2.5 py-1 font-mono text-[11px] hover:bg-accent"
            >
              {item.name}
            </span>
          ))}
        </div>
      </div>
    )

  return (
    <StepCard
      num="01"
      title={t('step1.ontologyGeneration')}
      status={status}
      statusText={statusText}
      active={phase === 0}
      apiNote="POST /api/graph/ontology/generate"
      description={t('step1.ontologyDesc')}
    >
      {phase === 0 && ontologyProgress && (
        <div className="mb-3 flex items-center gap-2 text-xs text-[#FF5722]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          <span>{ontologyProgress.message || t('step1.analyzingDocs')}</span>
        </div>
      )}

      {selected && (
        <OntologyDetailOverlay
          item={selected}
          resolveEntityName={resolveEntityName}
          onClose={() => setSelected(null)}
        />
      )}

      {tagList(projectData?.ontology?.entity_types, 'entity', t('step1.generatedEntityTypes'))}
      {tagList(projectData?.ontology?.edge_types, 'relation', t('step1.generatedRelationTypes'))}
    </StepCard>
  )
}
