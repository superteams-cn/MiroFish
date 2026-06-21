import { cn } from '@/lib/utils'

/**
 * 软进度条：灰底轨道 + 品牌渐变填充（带最小可见宽度下限）。
 * Step1~4 的「构建中/生成中」进度共用，统一轨道与渐变填充样式。
 */
export function SoftProgress({
  value,
  floor = 0,
  className,
}: {
  /** 进度百分比 0~100。 */
  value: number
  /** 最小可见宽度（百分比），避免起步时空条。 */
  floor?: number
  className?: string
}) {
  return (
    <div className={cn('bg-muted h-1.5 overflow-hidden rounded-full', className)}>
      <div
        className="bg-brand-gradient h-full rounded-full transition-all duration-500"
        style={{ width: `${Math.max(value, floor)}%` }}
      />
    </div>
  )
}
