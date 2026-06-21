import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** 合并 Tailwind 类名，自动处理冲突（shadcn/ui 约定）。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** 截断文本：超过 max 字符则截断并加省略号；空值返回空串。 */
export function truncate(text: string | undefined, max: number): string {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

/** 格式化时间为 `YYYY-MM-DD HH:mm`（本地时区的时分）；无效输入返回空串。 */
export function formatDateTime(s?: string): string {
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

/** 取文件扩展名（大写）；无扩展名返回 'FILE'。 */
export function fileExt(name?: string): string {
  return name?.split('.').pop()?.toUpperCase() || 'FILE'
}
