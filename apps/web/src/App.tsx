import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'

import { ErrorBoundary } from '@/components/ErrorBoundary'
import { router } from '@/router'

export default function App() {
  return (
    <ErrorBoundary>
      <RouterProvider router={router} />
      {/* 全局非阻塞提示 */}
      <Toaster richColors position="top-center" />
    </ErrorBoundary>
  )
}
