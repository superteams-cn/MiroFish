import { describe, expect, it } from 'vitest'

import {
  parseInsightForge,
  parseInterview,
  parsePanorama,
  parseQuickSearch,
  toResultText,
} from './step4-parsers'

/**
 * 这些测试用代表性的后端 markdown 文案作为固定输入，断言解析出的关键字段。
 * 目的：后端文案格式一改（标题/分隔符/字段措辞变化），这些断言能立刻抓到静默失效。
 */

describe('toResultText', () => {
  it('字符串原样返回', () => {
    expect(toResultText('hello')).toBe('hello')
  })
  it('null/undefined 返回空串', () => {
    expect(toResultText(null)).toBe('')
    expect(toResultText(undefined)).toBe('')
  })
  it('对象序列化为 JSON', () => {
    expect(toResultText({ a: 1 })).toBe('{"a":1}')
  })
})

describe('parseInsightForge', () => {
  const sample = `分析问题: 用户会不会买单
预测场景: 新品上市三个月内的市场反应
- 相关预测事实: 12
- 涉及实体: 5
- 关系链: 3

### 分析的子问题
1. 价格是否可接受
2. 渠道是否覆盖

### 【关键事实】
1. "目标人群对价格敏感"
2. "竞品已先发"

### 【核心实体】
- **小米**(公司)
  摘要: "主要竞争对手"
  相关事实: 4
- **张三**(用户)
  摘要: "典型早期采用者"
  相关事实: 2

### 【关系链】
- 小米 --[竞争]--> 本品牌
`

  it('解析查询/场景/统计', () => {
    const r = parseInsightForge(sample)
    expect(r.query).toBe('用户会不会买单')
    expect(r.simulationRequirement).toBe('新品上市三个月内的市场反应')
    expect(r.stats).toEqual({ facts: 12, entities: 5, relationships: 3 })
  })

  it('解析子问题/事实/实体/关系链', () => {
    const r = parseInsightForge(sample)
    expect(r.subQueries).toEqual(['价格是否可接受', '渠道是否覆盖'])
    expect(r.facts).toEqual(['目标人群对价格敏感', '竞品已先发'])
    expect(r.entities).toHaveLength(2)
    expect(r.entities[0]).toEqual({
      name: '小米',
      type: '公司',
      summary: '主要竞争对手',
      relatedFactsCount: 4,
    })
    expect(r.relations).toEqual([{ source: '小米', relation: '竞争', target: '本品牌' }])
  })

  it('空输入返回空骨架不抛错', () => {
    const r = parseInsightForge('')
    expect(r.query).toBe('')
    expect(r.facts).toEqual([])
    expect(r.entities).toEqual([])
    expect(r.relations).toEqual([])
    expect(r.stats).toEqual({ facts: 0, entities: 0, relationships: 0 })
  })
})

describe('parsePanorama', () => {
  const sample = `查询: 市场全景
- 总节点数: 20
- 总边数: 15
- 当前有效事实: 8
- 历史/过期事实: 3

### 【当前有效事实】
1. "用户活跃度上升"
2. "复购率稳定"

### 【历史/过期事实】
1. "早期定价过高"

### 【涉及实体】
- **品牌A**(公司)
- **品牌B**(公司)
`

  it('解析查询与统计', () => {
    const r = parsePanorama(sample)
    expect(r.query).toBe('市场全景')
    expect(r.stats).toEqual({ nodes: 20, edges: 15, activeFacts: 8, historicalFacts: 3 })
  })

  it('解析有效/历史事实与实体', () => {
    const r = parsePanorama(sample)
    expect(r.activeFacts).toEqual(['用户活跃度上升', '复购率稳定'])
    expect(r.historicalFacts).toEqual(['早期定价过高'])
    expect(r.entities).toEqual([
      { name: '品牌A', type: '公司' },
      { name: '品牌B', type: '公司' },
    ])
  })

  it('空输入返回空骨架', () => {
    const r = parsePanorama('')
    expect(r.query).toBe('')
    expect(r.activeFacts).toEqual([])
    expect(r.entities).toEqual([])
  })
})

describe('parseInterview', () => {
  const sample = `**采访主题:** 新品体验
**采访人数:** 2 / 3

### 采访对象选择理由
1. **张三**: 典型早期用户
2. **李四**: 价格敏感人群

---

### 采访实录

#### 采访 #1: 早期采用者
**张三** (产品爱好者)
_简介: 热衷尝鲜的年轻白领_

**Q:** 1. 你会买吗
2. 价格怎么看

**A:**
【Twitter平台回答】
我会考虑购买。

【Reddit平台回答】
价格再低点更好。

**关键引言:**
> "我会考虑购买"

#### 采访 #2: 价格敏感者
**李四** (精打细算)
_简介: 关注性价比_

**Q:** 1. 你怎么看

**A:**
【Twitter平台回答】
有点贵。

【Reddit平台回答】
观望中。

**关键引言:**
> "有点贵"

### 采访摘要与核心观点
整体接受度中等，价格是主要顾虑。
`

  it('解析主题/人数/选择理由', () => {
    const r = parseInterview(sample)
    expect(r.topic).toBe('新品体验')
    expect(r.successCount).toBe(2)
    expect(r.totalCount).toBe(3)
    expect(r.selectionReason).toContain('张三')
  })

  it('解析每条采访记录的关键字段', () => {
    const r = parseInterview(sample)
    expect(r.interviews).toHaveLength(2)
    const first = r.interviews[0]
    expect(first.name).toBe('张三')
    expect(first.role).toBe('产品爱好者')
    expect(first.bio).toBe('热衷尝鲜的年轻白领')
    expect(first.questions).toEqual(['你会买吗', '价格怎么看'])
    expect(first.twitterAnswer).toBe('我会考虑购买。')
    expect(first.redditAnswer).toBe('价格再低点更好。')
    expect(first.quotes).toEqual(['我会考虑购买'])
    expect(first.selectionReason).toContain('早期用户')
  })

  it('解析摘要', () => {
    const r = parseInterview(sample)
    expect(r.summary).toBe('整体接受度中等，价格是主要顾虑。')
  })

  it('空输入返回空骨架', () => {
    const r = parseInterview('')
    expect(r.topic).toBe('')
    expect(r.interviews).toEqual([])
    expect(r.summary).toBe('')
  })
})

describe('parseQuickSearch', () => {
  const sample = `搜索查询: 退货政策
找到 7 条相关结果

### 相关边:
- 用户 --[投诉]--> 客服

### 相关节点:
- **客服**(部门)
- 退货流程

### 相关事实:
1. 退货周期为7天
2. 需保留发票
`

  it('解析查询与计数', () => {
    const r = parseQuickSearch(sample)
    expect(r.query).toBe('退货政策')
    expect(r.count).toBe(7)
  })

  it('解析事实/边/节点', () => {
    const r = parseQuickSearch(sample)
    expect(r.facts).toEqual(['退货周期为7天', '需保留发票'])
    expect(r.edges).toEqual([{ source: '用户', relation: '投诉', target: '客服' }])
    expect(r.nodes).toEqual([
      { name: '客服', type: '部门' },
      { name: '退货流程', type: '' },
    ])
  })

  it('空输入返回空骨架', () => {
    const r = parseQuickSearch('')
    expect(r.query).toBe('')
    expect(r.count).toBe(0)
    expect(r.facts).toEqual([])
  })
})
