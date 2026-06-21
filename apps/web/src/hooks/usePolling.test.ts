import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { usePolling } from './usePolling'

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('不 start 时不调用回调', () => {
    const cb = vi.fn()
    renderHook(() => usePolling(cb, 1000))
    vi.advanceTimersByTime(5000)
    expect(cb).not.toHaveBeenCalled()
  })

  it('start 后按间隔周期调用；immediate=false 首帧在间隔之后', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => usePolling(cb, 1000))
    act(() => result.current.start())
    expect(cb).toHaveBeenCalledTimes(0) // 非 immediate：尚未到第一帧
    act(() => vi.advanceTimersByTime(1000))
    expect(cb).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(2000))
    expect(cb).toHaveBeenCalledTimes(3)
  })

  it('immediate=true 时 start 立即执行一次', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => usePolling(cb, 1000, { immediate: true }))
    act(() => result.current.start())
    expect(cb).toHaveBeenCalledTimes(1)
    act(() => vi.advanceTimersByTime(1000))
    expect(cb).toHaveBeenCalledTimes(2)
  })

  it('stop 后不再调用', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => usePolling(cb, 1000))
    act(() => result.current.start())
    act(() => vi.advanceTimersByTime(1000))
    expect(cb).toHaveBeenCalledTimes(1)
    act(() => result.current.stop())
    act(() => vi.advanceTimersByTime(5000))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('重复 start 不叠加定时器', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => usePolling(cb, 1000))
    act(() => result.current.start())
    act(() => result.current.start())
    act(() => result.current.start())
    act(() => vi.advanceTimersByTime(1000))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('始终调用最新的回调（不读过期闭包）', () => {
    const first = vi.fn()
    const second = vi.fn()
    const { result, rerender } = renderHook(({ cb }) => usePolling(cb, 1000), {
      initialProps: { cb: first },
    })
    act(() => result.current.start())
    rerender({ cb: second })
    act(() => vi.advanceTimersByTime(1000))
    expect(first).not.toHaveBeenCalled()
    expect(second).toHaveBeenCalledTimes(1)
  })

  it('卸载时自动清理定时器', () => {
    const cb = vi.fn()
    const { result, unmount } = renderHook(() => usePolling(cb, 1000))
    act(() => result.current.start())
    unmount()
    act(() => vi.advanceTimersByTime(5000))
    expect(cb).not.toHaveBeenCalled()
  })

  it('isActive 反映轮询状态', () => {
    const { result } = renderHook(() => usePolling(() => {}, 1000))
    expect(result.current.isActive()).toBe(false)
    act(() => result.current.start())
    expect(result.current.isActive()).toBe(true)
    act(() => result.current.stop())
    expect(result.current.isActive()).toBe(false)
  })
})
