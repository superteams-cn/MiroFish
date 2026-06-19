import { useTranslation } from 'react-i18next'
import {
  PenLine,
  Quote,
  Repeat2,
  Heart,
  MessageSquare,
  Search,
  UserPlus,
  ArrowBigUp,
  ArrowBigDown,
  MinusCircle,
  type LucideIcon,
} from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import type { ActionItem } from '@/lib/step3-types'

const TYPE_LABELS: Record<string, string> = {
  CREATE_POST: 'POST',
  REPOST: 'REPOST',
  LIKE_POST: 'LIKE',
  CREATE_COMMENT: 'COMMENT',
  LIKE_COMMENT: 'LIKE',
  DO_NOTHING: 'IDLE',
  FOLLOW: 'FOLLOW',
  SEARCH_POSTS: 'SEARCH',
  QUOTE_POST: 'QUOTE',
  UPVOTE_POST: 'UPVOTE',
  DOWNVOTE_POST: 'DOWNVOTE',
}

/** 动作类型徽章配色，按旧版语义分类：发帖 / 评论 / 互动 / 元操作 / 空闲。 */
const TYPE_COLORS: Record<string, string> = {
  // 发帖类
  CREATE_POST: 'bg-brand text-white',
  QUOTE_POST: 'bg-brand text-white',
  // 评论类
  CREATE_COMMENT: 'bg-blue-500 text-white',
  LIKE_COMMENT: 'bg-blue-500/15 text-blue-600',
  // 互动类
  REPOST: 'bg-secondary text-secondary-foreground',
  LIKE_POST: 'bg-rose-500/15 text-rose-600',
  UPVOTE_POST: 'bg-emerald-500/15 text-emerald-600',
  DOWNVOTE_POST: 'bg-amber-500/15 text-amber-600',
  // 元操作类
  FOLLOW: 'bg-muted text-muted-foreground border border-dashed',
  SEARCH_POSTS: 'bg-muted text-muted-foreground border border-dashed',
  // 空闲
  DO_NOTHING: 'bg-muted text-muted-foreground opacity-60',
}

/** 动作类型图标（与旧版正文图标对齐）。 */
const TYPE_ICONS: Record<string, LucideIcon> = {
  CREATE_POST: PenLine,
  QUOTE_POST: Quote,
  REPOST: Repeat2,
  LIKE_POST: Heart,
  CREATE_COMMENT: MessageSquare,
  LIKE_COMMENT: Heart,
  SEARCH_POSTS: Search,
  FOLLOW: UserPlus,
  UPVOTE_POST: ArrowBigUp,
  DOWNVOTE_POST: ArrowBigDown,
  DO_NOTHING: MinusCircle,
}

function label(type?: string) {
  return (type && TYPE_LABELS[type]) || type || 'UNKNOWN'
}
function badgeColor(type?: string) {
  return (type && TYPE_COLORS[type]) || 'bg-secondary text-secondary-foreground'
}
function truncate(content?: string, max = 100) {
  if (!content) return ''
  return content.length > max ? content.substring(0, max) + '...' : content
}
function actionTime(ts?: string) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

/**
 * 时间线中的单条 Agent 动作卡片，按动作类型渲染不同正文。
 * - variant="list"：自带左侧圆点与缩进（单轨列表）。
 * - variant="bare"：仅卡片本体，圆点由外层双轨时间线负责。
 */
export function ActionCard({
  action,
  variant = 'list',
}: {
  action: ActionItem
  variant?: 'list' | 'bare'
}) {
  const { t } = useTranslation()
  const args = action.action_args || {}
  const type = action.action_type
  const TypeIcon = type ? TYPE_ICONS[type] : undefined
  const isTwitter = action.platform === 'twitter'

  return (
    <div className={cn(variant === 'list' && 'relative pl-6')}>
      {variant === 'list' && (
        <span
          className={cn(
            'border-background absolute left-0 top-2 h-2.5 w-2.5 rounded-full border-2',
            isTwitter ? 'bg-sky-500' : 'bg-orange-500',
          )}
        />
      )}
      <div className="bg-card rounded-md border p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <Avatar className="h-6 w-6">
              <AvatarFallback className="text-[10px]">
                {(action.agent_name || 'A')[0]}
              </AvatarFallback>
            </Avatar>
            <span className="truncate text-xs font-semibold">{action.agent_name}</span>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            {action.platform && (
              <span
                className={cn(
                  'rounded px-1.5 py-0.5 text-[9px] font-bold uppercase',
                  isTwitter ? 'bg-sky-500/15 text-sky-600' : 'bg-orange-500/15 text-orange-600',
                )}
              >
                {isTwitter ? 'X' : 'Reddit'}
              </span>
            )}
            <span
              className={cn(
                'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold',
                badgeColor(type),
              )}
            >
              {TypeIcon && <TypeIcon className="h-3 w-3" />}
              {label(type)}
            </span>
          </div>
        </div>

        <div className="space-y-1.5 text-[11px] leading-relaxed">
          {type === 'CREATE_POST' && args.content && <p>{args.content}</p>}

          {type === 'QUOTE_POST' && (
            <>
              {args.quote_content && <p>{args.quote_content}</p>}
              {args.original_content && (
                <div className="border-muted bg-muted/40 rounded border-l-2 p-2">
                  <span className="text-muted-foreground text-[10px]">
                    @{args.original_author_name || 'User'}
                  </span>
                  <p>{truncate(args.original_content, 150)}</p>
                </div>
              )}
            </>
          )}

          {type === 'REPOST' && (
            <>
              <p className="text-muted-foreground">
                {t('step3.repostedFrom', { name: args.original_author_name || 'User' })}
              </p>
              {args.original_content && (
                <p className="bg-muted/40 rounded p-2">{truncate(args.original_content, 200)}</p>
              )}
            </>
          )}

          {type === 'LIKE_POST' && (
            <>
              <p className="text-muted-foreground">
                {t('step3.likedPost', { name: args.post_author_name || 'User' })}
              </p>
              {args.post_content && <p className="italic">"{truncate(args.post_content, 120)}"</p>}
            </>
          )}

          {type === 'CREATE_COMMENT' && (
            <>
              {args.content && <p>{args.content}</p>}
              {args.post_id && (
                <p className="text-muted-foreground text-[10px]">
                  {t('step3.replyToPost', { id: args.post_id })}
                </p>
              )}
            </>
          )}

          {type === 'SEARCH_POSTS' && (
            <p className="text-muted-foreground">
              {t('step3.searchQueryLabel')} <span className="font-mono">"{args.query || ''}"</span>
            </p>
          )}

          {type === 'FOLLOW' && (
            <p className="text-muted-foreground">
              {t('step3.followed', { name: args.target_user || args.user_id || 'User' })}
            </p>
          )}

          {(type === 'UPVOTE_POST' || type === 'DOWNVOTE_POST') && (
            <>
              <p className="text-muted-foreground">
                {type === 'UPVOTE_POST' ? t('step3.upvotedPost') : t('step3.downvotedPost')}
              </p>
              {args.post_content && <p className="italic">"{truncate(args.post_content, 120)}"</p>}
            </>
          )}

          {type === 'DO_NOTHING' && (
            <p className="text-muted-foreground">{t('step3.actionSkipped')}</p>
          )}

          {/* 通用回退 */}
          {![
            'CREATE_POST',
            'QUOTE_POST',
            'REPOST',
            'LIKE_POST',
            'CREATE_COMMENT',
            'SEARCH_POSTS',
            'FOLLOW',
            'UPVOTE_POST',
            'DOWNVOTE_POST',
            'DO_NOTHING',
          ].includes(type || '') &&
            args.content && <p>{args.content}</p>}
        </div>

        <div className="text-muted-foreground mt-2 text-[10px]">
          R{action.round_num} • {actionTime(action.timestamp)}
        </div>
      </div>
    </div>
  )
}
