import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { useDedupedLog } from './useDedupedLog'

describe('useDedupedLog', () => {
  it('首个 key 视为新；重复的同值返回 false', () => {
    const { result } = renderHook(() => useDedupedLog<string>())
    expect(result.current.isNew('a')).toBe(true)
    expect(result.current.isNew('a')).toBe(false)
  })

  it('值变化后再次返回 true', () => {
    const { result } = renderHook(() => useDedupedLog<string>())
    expect(result.current.isNew('a')).toBe(true)
    expect(result.current.isNew('b')).toBe(true)
    expect(result.current.isNew('b')).toBe(false)
    expect(result.current.isNew('a')).toBe(true) // 与「上一个」比较，非历史去重
  })

  it('支持数字等其他可比较类型', () => {
    const { result } = renderHook(() => useDedupedLog<number>(0))
    expect(result.current.isNew(0)).toBe(false) // 与初始值相同
    expect(result.current.isNew(1)).toBe(true)
    expect(result.current.isNew(1)).toBe(false)
  })

  it('reset 后回到初始值，下一个 key 重新算新', () => {
    const { result } = renderHook(() => useDedupedLog<string>())
    expect(result.current.isNew('a')).toBe(true)
    result.current.reset()
    expect(result.current.isNew('a')).toBe(true)
  })
})
