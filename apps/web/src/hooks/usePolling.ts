import { useCallback, useEffect, useRef } from 'react'

interface UsePollingOptions {
  /** 启动时是否立即执行一次回调（默认 false，与裸 setInterval 一致，首帧在 intervalMs 后）。 */
  immediate?: boolean
}

interface PollingHandle {
  /** 启动轮询。重复调用会先停掉上一轮再启新一轮（避免叠加多个定时器）。 */
  start: () => void
  /** 停止轮询（幂等）。 */
  stop: () => void
  /** 当前是否在轮询中。 */
  isActive: () => boolean
}

/**
 * 命令式轮询：以 intervalMs 周期调用最新的 callback，组件卸载时自动清理。
 *
 * 设计取舍：现有 4 处轮询都在「拿到 API 响应后」的任意时机命令式启停（而非随某个
 * enabled 布尔声明式开关），故本 hook 暴露 start/stop 句柄而非 enabled 入参。
 * - callback 始终取最新引用（存 ref），无需把它放进依赖、也不会因闭包过期读到旧值。
 * - start 内部先 stop，重复 start 不会叠加定时器（等价于原代码里「if (timer.current) return」+ 显式 stop 的两种写法）。
 * - immediate=false 时首次执行在 intervalMs 后（与裸 setInterval 行为一致）。
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  options: UsePollingOptions = {},
): PollingHandle {
  const { immediate = false } = options
  const callbackRef = useRef(callback)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // 始终指向最新回调，避免定时器闭包读到过期的 state/props
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const start = useCallback(() => {
    // 先停后启：重复 start 不叠加定时器
    if (timerRef.current !== null) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (immediate) void callbackRef.current()
    timerRef.current = setInterval(() => {
      void callbackRef.current()
    }, intervalMs)
  }, [immediate, intervalMs])

  const isActive = useCallback(() => timerRef.current !== null, [])

  // 卸载自动清理
  useEffect(() => stop, [stop])

  return { start, stop, isActive }
}
