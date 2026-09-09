"use client"

import { useEffect, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { staffHome, useAuth } from "@/lib/auth"

export default function StaffLoginPage() {
  const router = useRouter()
  const { staff, status, login } = useAuth()
  const [loginValue, setLoginValue] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (status === "authenticated" && staff) {
      router.replace(staffHome(staff.role))
    }
  }, [router, staff, status])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const profile = await login(loginValue, password)
      setPassword("")
      router.replace(staffHome(profile.role))
    } catch {
      setError("Unable to sign in with those credentials.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="m-auto w-full max-w-md p-6">
      <Card>
        <CardHeader>
          <CardTitle>Staff sign in</CardTitle>
          <CardDescription>For authorized Otklik staff only.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="login">Login</Label>
              <Input
                id="login"
                name="login"
                autoComplete="username"
                required
                value={loginValue}
                onChange={(event) => setLoginValue(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <Button className="w-full" type="submit" disabled={submitting}>
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
