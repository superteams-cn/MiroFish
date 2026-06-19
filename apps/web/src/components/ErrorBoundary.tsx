import { Component, type ErrorInfo, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
}
interface State {
  error: Error | null
}

/** 全局错误边界：捕获渲染期异常，展示兜底页而非整页白屏。 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('页面渲染异常:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
          <h1 className="text-xl font-bold">页面出错了</h1>
          <p className="text-muted-foreground max-w-md text-sm">{this.state.error.message}</p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => this.setState({ error: null })}>
              重试
            </Button>
            <Button onClick={() => (window.location.href = '/')}>返回首页</Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
