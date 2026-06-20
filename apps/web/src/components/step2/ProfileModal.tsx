import { useTranslation } from 'react-i18next'

import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import type { PersonaDimensions, Profile } from '@/lib/step2-types'

interface Props {
  profile: Profile | null
  /** 这个人在推演开始前已经发出的声音（AI 埋下的初始帖子），是对其画像的补充 */
  posts?: string[]
  onClose: () => void
}

/**
 * 人设四维度框架。
 * `key` 对应后端 dimensions 对象字段；有真实内容时展示真实内容，
 * 否则回退到 descKey 注解式展示（向后兼容旧版单一 persona 文本）。
 */
const PERSONA_DIMENSIONS = [
  {
    key: 'experience',
    titleKey: 'step2.personaDimExperience',
    descKey: 'step2.personaDimExperienceDesc',
  },
  {
    key: 'behavior',
    titleKey: 'step2.personaDimBehavior',
    descKey: 'step2.personaDimBehaviorDesc',
  },
  { key: 'memory', titleKey: 'step2.personaDimMemory', descKey: 'step2.personaDimMemoryDesc' },
  { key: 'social', titleKey: 'step2.personaDimSocial', descKey: 'step2.personaDimSocialDesc' },
] as const satisfies ReadonlyArray<{
  key: keyof PersonaDimensions
  titleKey: string
  descKey: string
}>

/** Agent 人设详情模态框（基于 shadcn Dialog）。 */
export function ProfileModal({ profile, posts = [], onClose }: Props) {
  const { t } = useTranslation()

  const genderMap: Record<string, string> = {
    male: t('step2.genderMale'),
    female: t('step2.genderFemale'),
    other: t('step2.genderOther'),
  }

  // 是否存在后端产出的真实四维度内容（任一维度非空即视为有）
  const hasDimensions = PERSONA_DIMENSIONS.some((dim) => profile?.dimensions?.[dim.key]?.trim())

  return (
    <Dialog open={!!profile} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl gap-0 overflow-y-auto">
        {profile && (
          <>
            {/* 头部：渐变头像 + 姓名 / @ / 职业 */}
            <DialogHeader className="flex-row items-center gap-4 space-y-0 pr-8">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-xl font-semibold text-white shadow-lg shadow-indigo-500/25">
                {(profile.name || profile.username || '?').slice(0, 1)}
              </div>
              <div className="min-w-0">
                <DialogTitle className="flex items-baseline gap-2 text-xl">
                  <span className="truncate">{profile.name || profile.username}</span>
                  <span className="text-muted-foreground shrink-0 font-mono text-xs font-normal">
                    @{profile.username}
                  </span>
                </DialogTitle>
                {profile.profession && (
                  <span className="mt-1.5 inline-block rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs text-indigo-600 dark:text-indigo-300">
                    {profile.profession}
                  </span>
                )}
              </div>
            </DialogHeader>

            <div className="mt-5 space-y-5">
              {/* 基本信息：玻璃质感小卡 */}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Info
                  label={t('step2.profileModalAge')}
                  value={`${profile.age ?? '-'} ${t('step2.yearsOld')}`}
                />
                <Info
                  label={t('step2.profileModalGender')}
                  value={genderMap[profile.gender ?? ''] || profile.gender || '-'}
                />
                <Info label={t('step2.profileModalCountry')} value={profile.country || '-'} />
                <Info label={t('step2.profileModalMbti')} value={profile.mbti || '-'} />
              </div>

              <Section label={t('step2.profileModalBio')}>
                <p className="text-foreground/80 text-sm leading-relaxed">
                  {profile.bio || t('step2.noBio')}
                </p>
              </Section>

              {!!posts.length && (
                <Section label={t('step2.cSaid')}>
                  <div className="space-y-2">
                    {posts.map((post, idx) => (
                      <p
                        key={idx}
                        className="text-foreground/85 rounded-xl border-l-2 border-indigo-400/70 bg-indigo-500/[0.06] p-3 text-sm leading-relaxed"
                      >
                        {post}
                      </p>
                    ))}
                  </div>
                </Section>
              )}

              {!!profile.interested_topics?.length && (
                <Section label={t('step2.profileModalTopics')}>
                  <div className="flex flex-wrap gap-1.5">
                    {profile.interested_topics.map((topic) => (
                      <Badge key={topic} variant="secondary" className="rounded-full font-normal">
                        {topic}
                      </Badge>
                    ))}
                  </div>
                </Section>
              )}

              {hasDimensions ? (
                /* 真实四维度内容：后端 dimensions 字段产出 */
                <Section label={t('step2.profileModalPersona')}>
                  <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                    {PERSONA_DIMENSIONS.map((dim) => {
                      const content = profile.dimensions?.[dim.key]?.trim()
                      return (
                        <div
                          key={dim.key}
                          className="rounded-xl border border-indigo-500/15 bg-indigo-500/[0.03] p-3"
                        >
                          <span className="flex items-center gap-1.5 text-xs font-semibold">
                            <span className="h-1.5 w-1.5 rounded-full bg-gradient-to-br from-indigo-500 to-fuchsia-500" />
                            {t(dim.titleKey)}
                          </span>
                          <p className="text-foreground/75 mt-1.5 whitespace-pre-wrap text-xs leading-relaxed">
                            {content || t('step2.personaDimEmpty')}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                </Section>
              ) : (
                profile.persona && (
                  <Section label={t('step2.profileModalPersona')}>
                    {/* 向后兼容：无 dimensions 时回退到注解式四维框架 + 单一 persona 文本 */}
                    <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
                      {PERSONA_DIMENSIONS.map((dim) => (
                        <div
                          key={dim.key}
                          className="rounded-xl border border-indigo-500/15 bg-indigo-500/[0.03] p-2.5"
                        >
                          <span className="block text-[11px] font-semibold">{t(dim.titleKey)}</span>
                          <span className="text-muted-foreground mt-0.5 block text-[10px] leading-snug">
                            {t(dim.descKey)}
                          </span>
                        </div>
                      ))}
                    </div>
                    <p className="bg-secondary text-foreground/80 whitespace-pre-wrap rounded-xl p-3 text-xs leading-relaxed">
                      {profile.persona}
                    </p>
                  </Section>
                )
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-secondary rounded-xl px-3 py-2.5">
      <span className="text-muted-foreground block text-[10px]">{label}</span>
      <span className="mt-0.5 block text-sm font-semibold">{value}</span>
    </div>
  )
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <span className="text-foreground/90 mb-2 block text-xs font-semibold">{label}</span>
      {children}
    </div>
  )
}
