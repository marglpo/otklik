import { DevelopmentDiagnostics } from "@/components/development-diagnostics"

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center bg-zinc-50 px-6 py-16 font-sans dark:bg-black">
      <main className="flex w-full max-w-2xl flex-col gap-10 rounded-2xl bg-white p-8 shadow-sm ring-1 ring-black/5 dark:bg-zinc-950 dark:ring-white/10 sm:p-12">
        <div className="space-y-4">
          <p className="text-sm font-medium tracking-wide text-zinc-500 uppercase">
            Infrastructure foundation
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-zinc-950 dark:text-zinc-50">
            Otklik
          </h1>
          <p className="max-w-xl text-lg leading-8 text-zinc-600 dark:text-zinc-400">
            A privacy-first foundation for trusted anonymous appeals. Business
            workflows are intentionally not part of this phase.
          </p>
        </div>

        <DevelopmentDiagnostics />
      </main>
    </div>
  );
}
