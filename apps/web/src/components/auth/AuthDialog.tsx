import { useEffect, useRef, useState } from 'react'
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
import { TextButton } from '@/components/ui/text-button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { OtpInput } from '@/components/auth/OtpInput'
import { resetPasswordWithCode, sendCode, type CodePurpose } from '@/lib/api/auth'
import { cn } from '@/lib/utils'
import { useAuth } from '@/stores/auth'

/** 从（已被拦截器归一化的）错误中取文案，回退到通用提示。 */
function extractError(e: unknown, fallback: string): string {
  return (e as Error)?.message || fallback
}

const SEND_COOLDOWN = 60
type LoginMethod = 'password' | 'code'

/** 登录/注册/忘记密码弹框：密码与验证码双通道，单弹框内切换。由 AuthProvider 控制开合。 */
export function AuthDialog() {
  const { t } = useTranslation()
  const { dialogOpen, dialogMode, setDialogMode, closeAuth, login, loginWithCode, register } =
    useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [code, setCode] = useState('')
  const [loginMethod, setLoginMethod] = useState<LoginMethod>('password')
  const [submitting, setSubmitting] = useState(false)
  const [sending, setSending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const timerRef = useRef<number>()

  const isRegister = dialogMode === 'register'
  const isForgot = dialogMode === 'forgot'
  const isLogin = dialogMode === 'login'
  // 需要验证码的场景：验证码登录 / 注册 / 找回密码
  const usesCode = (isLogin && loginMethod === 'code') || isRegister || isForgot
  const codePurpose: CodePurpose = isRegister ? 'register' : isForgot ? 'reset' : 'login'

  // 打开/切换模式时清空敏感输入
  useEffect(() => {
    if (dialogOpen) {
      setPassword('')
      setCode('')
      setSubmitting(false)
    }
  }, [dialogOpen, dialogMode])

  useEffect(() => {
    if (cooldown <= 0) return
    timerRef.current = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(timerRef.current)
  }, [cooldown])

  const onSendCode = async () => {
    if (sending || cooldown > 0) return
    if (!email.trim()) {
      toast.error(t('auth.invalidEmail'))
      return
    }
    setSending(true)
    try {
      await sendCode(email.trim(), codePurpose)
      toast.success(t('auth.codeSent'))
      setCooldown(SEND_COOLDOWN)
    } catch (err) {
      toast.error(extractError(err, t('auth.genericError')))
    } finally {
      setSending(false)
    }
  }

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (submitting) return
    setSubmitting(true)
    try {
      if (isForgot) {
        await resetPasswordWithCode(email.trim(), code, password)
        toast.success(t('auth.resetSuccess'))
        setDialogMode('login')
      } else if (isRegister) {
        await register(email.trim(), password, code, displayName.trim() || undefined)
        toast.success(t('auth.signUpSuccess'))
      } else if (loginMethod === 'code') {
        await loginWithCode(email.trim(), code)
        toast.success(t('auth.signInSuccess'))
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
    ? t('auth.submitReset')
    : isRegister
      ? t('auth.submitSignUp')
      : loginMethod === 'code'
        ? t('auth.submitCodeLogin')
        : t('auth.submitSignIn')
  // 找回密码用新密码，注册/密码登录用密码
  const showPassword = isRegister || isForgot || (isLogin && loginMethod === 'password')
  const passwordLabel = isForgot ? t('auth.newPasswordLabel') : t('auth.passwordLabel')

  return (
    <Dialog open={dialogOpen} onOpenChange={(open) => !open && !submitting && closeAuth()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="text-xl">{title}</DialogTitle>
          <DialogDescription>{subtitle}</DialogDescription>
        </DialogHeader>

        {/* 登录方式切换：密码 / 验证码 */}
        {isLogin && (
          <div className="bg-muted/60 flex rounded-lg p-1">
            {(['password', 'code'] as LoginMethod[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setLoginMethod(m)}
                className={cn(
                  'flex-1 rounded-md py-1.5 text-sm font-medium transition-colors',
                  loginMethod === m
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {m === 'password' ? t('auth.passwordLogin') : t('auth.codeLogin')}
              </button>
            ))}
          </div>
        )}

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

          {showPassword && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="auth-password">{passwordLabel}</Label>
                {isLogin && loginMethod === 'password' && (
                  <TextButton onClick={() => setDialogMode('forgot')} className="text-xs">
                    {t('auth.forgotPassword')}
                  </TextButton>
                )}
              </div>
              <Input
                id="auth-password"
                type="password"
                autoComplete={isRegister || isForgot ? 'new-password' : 'current-password'}
                required
                minLength={isRegister || isForgot ? 8 : undefined}
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

          {usesCode && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('auth.verifyCodeLabel')}</Label>
                <button
                  type="button"
                  onClick={onSendCode}
                  disabled={sending || cooldown > 0}
                  className="text-primary text-xs font-medium hover:underline disabled:opacity-50"
                >
                  {cooldown > 0 ? t('auth.sendCodeIn', { sec: cooldown }) : t('auth.sendCode')}
                </button>
              </div>
              <OtpInput value={code} onChange={setCode} focusOnMount={false} />
            </div>
          )}

          <Button
            type="submit"
            className="w-full gap-2"
            disabled={submitting || (usesCode && code.length < 6)}
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? t('auth.submitting') : submitLabel}
          </Button>
        </form>

        <TextButton
          onClick={() => setDialogMode(isRegister || isForgot ? 'login' : 'register')}
          className="mx-auto text-sm"
        >
          {isForgot
            ? t('auth.backToSignIn')
            : isRegister
              ? t('auth.switchToSignIn')
              : t('auth.switchToSignUp')}
        </TextButton>
      </DialogContent>
    </Dialog>
  )
}
