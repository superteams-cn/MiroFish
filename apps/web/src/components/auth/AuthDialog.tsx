import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { forgotPassword } from '@/lib/api/auth'
import { useAuth } from '@/stores/auth'

/** 从 axios 错误中取后端本地化错误文案，回退到通用提示。 */
function extractError(e: unknown, fallback: string): string {
  const resp = (e as { response?: { data?: { error?: string } } })?.response
  return resp?.data?.error || (e as Error)?.message || fallback
}

/** 登录/注册/忘记密码弹框：单弹框内切换三种模式。由 AuthProvider 控制开合。 */
export function AuthDialog() {
  const { t } = useTranslation()
  const { dialogOpen, dialogMode, setDialogMode, closeAuth, login, register } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isRegister = dialogMode === 'register'
  const isForgot = dialogMode === 'forgot'

  // 每次打开/切换模式时清空敏感输入，避免残留
  useEffect(() => {
    if (dialogOpen) {
      setPassword('')
      setSubmitting(false)
    }
  }, [dialogOpen, dialogMode])

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      if (isForgot) {
        await forgotPassword(email.trim())
        toast.success(t('auth.resetEmailSent'))
        setDialogMode('login')
      } else if (isRegister) {
        await register(email.trim(), password, displayName.trim() || undefined)
        toast.success(t('auth.signUpSuccess'))
      } else {
        await login(email.trim(), password)
        toast.success(t('auth.signInSuccess'))
      }
    } catch (err) {
      toast.error(extractError(err, t('auth.genericError')))
    } finally {
      setSubmitting(false)
    }
  }

  const title = isForgot
    ? t('auth.forgotTitle')
    : isRegister
      ? t('auth.signUpTitle')
      : t('auth.signInTitle')
  const subtitle = isForgot
    ? t('auth.forgotSubtitle')
    : isRegister
      ? t('auth.signUpSubtitle')
      : t('auth.signInSubtitle')
  const submitLabel = isForgot
    ? t('auth.sendResetLink')
    : isRegister
      ? t('auth.submitSignUp')
      : t('auth.submitSignIn')

  return (
    <Dialog open={dialogOpen} onOpenChange={(open) => !open && !submitting && closeAuth()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-xl">{title}</DialogTitle>
          <DialogDescription>{subtitle}</DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="auth-email">{t('auth.emailLabel')}</Label>
            <Input
              id="auth-email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('auth.emailPlaceholder')}
            />
          </div>

          {!isForgot && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="auth-password">{t('auth.passwordLabel')}</Label>
                {!isRegister && (
                  <button
                    type="button"
                    onClick={() => setDialogMode('forgot')}
                    className="text-muted-foreground hover:text-foreground text-xs transition-colors"
                  >
                    {t('auth.forgotPassword')}
                  </button>
                )}
              </div>
              <Input
                id="auth-password"
                type="password"
                autoComplete={isRegister ? 'new-password' : 'current-password'}
                required
                minLength={isRegister ? 8 : undefined}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('auth.passwordPlaceholder')}
              />
            </div>
          )}

          {isRegister && (
            <div className="space-y-1.5">
              <Label htmlFor="auth-name">{t('auth.displayNameOptional')}</Label>
              <Input
                id="auth-name"
                type="text"
                autoComplete="nickname"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder={t('auth.displayNamePlaceholder')}
              />
            </div>
          )}

          <Button type="submit" className="w-full gap-2" disabled={submitting}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? t('auth.submitting') : submitLabel}
          </Button>
        </form>

        <button
          type="button"
          onClick={() => setDialogMode(isRegister || isForgot ? 'login' : 'register')}
          className="text-muted-foreground hover:text-foreground mx-auto text-sm transition-colors"
        >
          {isForgot
            ? t('auth.backToSignIn')
            : isRegister
              ? t('auth.switchToSignIn')
              : t('auth.switchToSignUp')}
        </button>
      </DialogContent>
    </Dialog>
  )
}
