"use client"

import { Cloud, Loader2, LockKeyhole } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { cn } from "@/lib/utils"

type LoginFormProps = React.ComponentProps<"div"> & {
  error?: string | null
  isLoading?: boolean
  onGoogleSignIn?: () => void
}

function GoogleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="size-4">
      <path
        d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
        fill="currentColor"
      />
    </svg>
  )
}

export function LoginForm({
  className,
  error,
  isLoading = false,
  onGoogleSignIn,
  ...props
}: LoginFormProps) {
  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <FieldGroup>
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex size-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Cloud className="size-5" />
          </div>
          <div className="space-y-1">
            <h1 className="text-xl font-bold">Sync Riskfolio</h1>
            <FieldDescription>
              Sign in only if you want portfolios saved to your Supabase cloud
              account.
            </FieldDescription>
          </div>
        </div>

        <Field>
          <Button
            type="button"
            disabled={isLoading || !onGoogleSignIn}
            onClick={onGoogleSignIn}
          >
            {isLoading ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <GoogleIcon />
            )}
            Continue with Google
          </Button>
        </Field>

        {error && (
          <p className="text-sm text-destructive" role="alert">
            {error}
          </p>
        )}

        <Field className="rounded-md border bg-muted/50 p-3">
          <FieldLabel className="flex items-center gap-2 text-sm">
            <LockKeyhole className="size-4" />
            Local-first privacy
          </FieldLabel>
          <FieldDescription>
            You can keep using local browser storage without signing in. Cloud
            sync starts only after Google sign-in.
          </FieldDescription>
        </Field>
      </FieldGroup>
    </div>
  )
}
