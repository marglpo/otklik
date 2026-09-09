"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { CrisisPanel } from "@/components/appeals/crisis-panel"
import { PublicShell } from "@/components/appeals/public-shell"
import { Button } from "@/components/ui/button"
import type { CurrentAppeal } from "@/lib/appeals"
import { publicAppealsApi } from "@/lib/appeals"

export default function CurrentAppealPage() {
  const router = useRouter()
  const [appeal, setAppeal] = useState<CurrentAppeal | null>(null)
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    publicAppealsApi
      .current(controller.signal)
      .then(setAppeal)
      .catch(() => setUnavailable(true))
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  async function leave() {
    await publicAppealsApi.leave()
    router.replace("/")
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-2xl space-y-6 py-10">
        {loading ? (
          <div className="rounded-3xl bg-white p-8 text-slate-600 ring-1 ring-slate-200">
            Загружаем статус…
          </div>
        ) : null}

        {unavailable ? (
          <div className="space-y-4 rounded-3xl bg-white p-8 ring-1 ring-slate-200">
            <h1 className="text-2xl font-semibold">Нужно снова ввести номер</h1>
            <p className="leading-7 text-slate-600">
              Временный безопасный доступ закончился или не был открыт в этом браузере.
            </p>
            <Link className="font-medium text-teal-700 underline" href="/appeal/check">
              Перейти к проверке обращения
            </Link>
          </div>
        ) : null}

        {appeal ? (
          <>
            <div className="rounded-3xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-9">
              <p className="text-sm font-semibold text-teal-700">Текущий статус</p>
              <h1 className="mt-2 text-3xl font-semibold">{appeal.status_text}</h1>
              {appeal.category ? (
                <p className="mt-4 text-sm text-slate-600">Тема: {appeal.category.name}</p>
              ) : null}
              <p className="mt-2 text-xs text-slate-500">
                Обновлено {new Date(appeal.updated_at).toLocaleString("ru-RU")}
              </p>
              {appeal.rejection_reason ? (
                <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-6 text-slate-700">
                  {appeal.rejection_reason}
                </div>
              ) : null}
            </div>

            <div className="rounded-2xl bg-white p-6 ring-1 ring-slate-200">
              <h2 className="font-semibold">История статуса</h2>
              <ol className="mt-5 space-y-5">
                {appeal.timeline.map((item, index) => (
                  <li key={`${item.status}-${item.occurred_at}`} className="flex gap-4">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-teal-100 text-sm font-semibold text-teal-800">
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-medium">{item.text}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {new Date(item.occurred_at).toLocaleString("ru-RU")}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            {appeal.show_crisis_support ? (
              <CrisisPanel resources={appeal.crisis_support_resources} />
            ) : null}

            <Button type="button" variant="outline" className="w-full" onClick={leave}>
              Закрыть доступ на этом устройстве
            </Button>
          </>
        ) : null}
      </section>
    </PublicShell>
  )
}
