/**
 * 集中式 UI 元数据：跨组件复用的「分类色板」。
 *
 * 这些是语义【分类色】（平台 / 工具 / 状态），不同于主题语义令牌
 * （bg-background / text-foreground 等，由 CSS 变量驱动、随明暗模式翻转）。
 * 分类色本身需要稳定的具体色相来区分类别，但应在此单点定义，
 * 避免在各业务组件里重复硬编码同一套 sky/orange/violet… 字符串。
 *
 * 注意：所有类名都以「完整字面量」形式出现，Tailwind JIT 才能正确收录。
 */

// ---- 平台（双轨：信息广场 twitter / 话题社区 reddit）----

export type Platform = 'twitter' | 'reddit'

export interface PlatformMeta {
  /** 实心圆点 / 标记 */
  dot: string
  /** 纯文字强调 */
  text: string
  /** 柔和徽章（浅底 + 同色文字） */
  badge: string
}

export const PLATFORM_META: Record<Platform, PlatformMeta> = {
  twitter: {
    dot: 'bg-sky-500',
    text: 'text-sky-500',
    badge: 'bg-sky-500/15 text-sky-600',
  },
  reddit: {
    dot: 'bg-orange-500',
    text: 'text-orange-500',
    badge: 'bg-orange-500/15 text-orange-600',
  },
}

/** 按 platform 字段取平台元数据；非 twitter 一律落到 reddit（右轨）。 */
export function platformMeta(platform?: string | null): PlatformMeta {
  return platform === 'twitter' ? PLATFORM_META.twitter : PLATFORM_META.reddit
}

// ---- 工具强调色（柔和徽章：text-x-500 + bg-x-500/10）----
// ReportAgent 的专业工具用一组固定色相区分；step4 / step5 共用同一套色板。

export type AccentName = 'violet' | 'blue' | 'green' | 'orange' | 'cyan' | 'pink'

export const ACCENT_SOFT: Record<AccentName, string> = {
  violet: 'text-violet-500 bg-violet-500/10',
  blue: 'text-blue-500 bg-blue-500/10',
  green: 'text-green-500 bg-green-500/10',
  orange: 'text-orange-500 bg-orange-500/10',
  cyan: 'text-cyan-500 bg-cyan-500/10',
  pink: 'text-pink-500 bg-pink-500/10',
}

// ---- 语义状态文字色（成功 / 失败 / 警告）----
// 区别于 StatusDot 的圆点配色；用于行内成功提示、校验结果等文字场景。

export const STATUS_TEXT = {
  success: 'text-green-600',
  error: 'text-red-600',
  warning: 'text-amber-500',
} as const

export type StatusTextKind = keyof typeof STATUS_TEXT
