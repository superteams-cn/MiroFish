import { useTranslation } from 'react-i18next'
import { LogOut, User } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/stores/auth'

/** 顶栏鉴权入口：未登录显示「登录」按钮，已登录显示头像下拉。 */
export function AuthButton() {
  const { t } = useTranslation()
  const { user, ready, openAuth, logout } = useAuth()

  // 启动引导未完成时不抢先渲染，避免「登录 → 头像」的闪烁
  if (!ready) return null

  if (!user) {
    return (
      <Button
        variant="secondary"
        size="sm"
        className="gap-1.5 rounded-full"
        onClick={() => openAuth('login')}
      >
        <User className="h-4 w-4" />
        <span className="hidden sm:inline">{t('auth.signIn')}</span>
      </Button>
    )
  }

  const initial = (user.display_name || user.email || '?').slice(0, 1).toUpperCase()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="focus-visible:ring-ring rounded-full focus-visible:outline-none focus-visible:ring-2"
          aria-label={t('auth.account')}
        >
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-sm font-semibold text-white">
              {initial}
            </AvatarFallback>
          </Avatar>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="px-2 py-1.5">
          <p className="truncate text-sm font-medium">{user.display_name || t('auth.account')}</p>
          <p className="text-muted-foreground truncate text-xs">{user.email}</p>
        </div>
        <DropdownMenuItem
          onClick={() => {
            logout()
            toast.success(t('auth.loggedOut'))
          }}
          className="text-destructive focus:text-destructive gap-2"
        >
          <LogOut className="h-4 w-4" />
          {t('auth.logout')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
