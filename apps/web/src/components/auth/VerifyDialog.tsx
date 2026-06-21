import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Loader2, MailCheck } from 'lucide-react'
import { toast } from 'sonner'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { OtpInput } from '@/components/auth/OtpInput'
import { useAuth } from '@/stores/auth'

/** 从 axios 错误中取后端本地化错误文案，回退到通用提示。 */
function extractError(e: unknown, fallback: string): string {
  return (e as Error)?.message || fallback
}

const RESEND_COOLDOWN = 60

interface VerifyDialogProps {
  open: boolean
  onClose: () => void
}

/** 邮箱验证弹框：输入 6 位验证码确认，或重发邮件（带倒计时）。链接验证仍并行可用。 */
export function VerifyDialog({ open, onClose }: VerifyDialogProps) {
  const { t } = useTranslation()
  const { user, verifyWithCode, resendVerification } = useAuth()

  const [code, setCode] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [resending, setResending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const timerRef = useRef<number>()

  // 打开时重置；关闭时清理倒计时
  useEffect(() => {
    if (open) {
      setCode('')
      setSubmitting(false)
    }
  }, [open])

  useEffect(() => {
    if (cooldown <= 0) return
    timerRef.current = window.setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => window.clearTimeout(timerRef.current)
  }, [cooldown])

  const submitCode = async (value: string) => {
    if (submitting || value.length < 6) return
    setSubmitting(true)
    try {
      await verifyWithCode(value.trim())
      toast.success(t('auth.verifySuccess'))
      onClose()
    } catch (err) {
      toast.error(extractError(err, t('auth.invalidVerifyCode')))
    } finally {
      setSubmitting(false)
    }
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void submitCode(code)
  }

  const onResend = async () => {
    if (resending || cooldown > 0) return
    setResending(true)
    try {
      const msg = await resendVerification()
      toast.success(msg || t('auth.verifyEmailSent'))
      setCooldown(RESEND_COOLDOWN)
    } catch (err) {
      toast.error(extractError(err, t('auth.genericError')))
    } finally {
      setResending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && !submitting && onClose()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-xl">
            <MailCheck className="text-primary h-5 w-5" />
            {t('auth.verifyDialogTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('auth.verifyDialogSubtitle', { email: user?.email || '' })}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>{t('auth.verifyCodeLabel')}</Label>
            <OtpInput value={code} onChange={setCode} onComplete={(v) => void submitCode(v)} />
          </div>

          <Button type="submit" className="w-full gap-2" disabled={submitting || code.length < 6}>
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {submitting ? t('auth.submitting') : t('auth.submitVerifyCode')}
          </Button>
        </form>

        <button
          type="button"
          onClick={onResend}
          disabled={resending || cooldown > 0}
          className="text-muted-foreground hover:text-foreground mx-auto text-sm transition-colors disabled:opacity-50"
        >
          {cooldown > 0 ? t('auth.resendIn', { sec: cooldown }) : t('auth.resend')}
        </button>
      </DialogContent>
    </Dialog>
  )
}
