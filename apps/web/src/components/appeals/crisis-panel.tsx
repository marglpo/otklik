import type { CrisisResource } from "@/lib/appeals"

export function CrisisPanel({ resources }: { resources: CrisisResource[] }) {
  return (
    <aside className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
      {resources.map((resource) => (
        <div key={`${resource.title}-${resource.message}`} className="space-y-2">
          <h2 className="font-semibold">{resource.title}</h2>
          <p className="text-sm leading-6">{resource.message}</p>
          <div className="flex flex-wrap gap-3 text-sm font-medium">
            {resource.phone ? <a href={`tel:${resource.phone}`}>{resource.phone}</a> : null}
            {resource.url ? (
              <a href={resource.url} rel="noreferrer" target="_blank">
                Открыть ресурс помощи
              </a>
            ) : null}
          </div>
        </div>
      ))}
      <p className="text-xs text-amber-800">
        Эта подсказка не мешает отправить или просматривать обращение.
      </p>
    </aside>
  )
}
