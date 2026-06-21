import * as React from 'react'

import { cn } from '@/lib/utils'

/**
 * 文字操作按钮：低强调的「次要文字链」——常态 muted、hover 转 foreground。
 *
 * 用于返回 / 取消 / 切换 / 重发等次级动作（区别于 `<Button>` 的实心/描边/渐变样式）。
 * 收口此前各处手写的 `text-muted-foreground hover:text-foreground transition-colors`，
 * 布局类（flex/padding/字号/边框）仍由调用方按需通过 className 传入。
 */
const TextButton = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, type = 'button', ...props }, ref) => (
  <button
    ref={ref}
    type={type}
    className={cn(
      'text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50',
      className,
    )}
    {...props}
  />
))
TextButton.displayName = 'TextButton'

export { TextButton }
