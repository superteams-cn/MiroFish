import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AuthDialog } from '@/components/auth/AuthDialog'
import { AuthProvider } from '@/stores/auth'
import { router } from '@/router'

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <RouterProvider router={router} />
        {/* 全局登录/注册弹框，任意路由可弹出 */}
        <AuthDialog />
        {/* 全局非阻塞提示 */}
        <Toaster richColors position="top-center" />
      </AuthProvider>
    </ErrorBoundary>
  )
}
