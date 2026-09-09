import Link from "next/link"
import type { ReactNode } from "react"

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dff8f0,transparent_40%),linear-gradient(to_bottom,#f8fffc,#f7f8fc)] text-slate-950">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-5 py-5">
        <Link href="/" className="text-xl font-semibold tracking-tight text-teal-950">
          Отклик
        </Link>
        <p className="rounded-full bg-white/80 px-3 py-1 text-xs text-slate-600 ring-1 ring-slate-200">
          Без регистрации
        </p>
      </header>
      <main className="mx-auto w-full max-w-5xl px-5 pb-16">{children}</main>
    </div>
  )
}
