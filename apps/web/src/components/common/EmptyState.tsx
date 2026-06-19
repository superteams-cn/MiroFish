import type { LucideIcon } from 'lucide-react'
import { Inbox } from 'lucide-react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  /** 图标，默认收件箱 */
  icon?: LucideIcon
  title: string
  description?: string
  /** 操作区（按钮等） */
  action?: React.ReactNode
  className?: string
}

/** 统一空状态：图标 + 标题 + 说明 + 可选操作。 */
export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex h-full flex-col items-center justify-center gap-2 p-6 text-center',
        className,
      )}
    >
      <Icon className="text-muted-foreground/60 h-8 w-8" />
      <p className="text-sm font-medium">{title}</p>
      {description && <p className="text-muted-foreground max-w-xs text-xs">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
