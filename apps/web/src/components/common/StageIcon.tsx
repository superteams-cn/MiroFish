import { CheckCircle2, Loader2 } from 'lucide-react'

import { cn } from '@/lib/utils'

/**
 * 旅程舞台标题图标：品牌渐变圆角方盒，完成显示对勾、进行中显示旋转加载。
 * Step1~4 舞台标题共用，统一图标盒尺寸与渐变来源（.bg-brand-gradient）。
 */
export function StageIcon({ done, className }: { done: boolean; className?: string }) {
  return (
    <div
      className={cn(
        'bg-brand-gradient mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl text-white shadow-lg',
        className,
      )}
    >
      {done ? <CheckCircle2 className="h-8 w-8" /> : <Loader2 className="h-8 w-8 animate-spin" />}
    </div>
  )
}
