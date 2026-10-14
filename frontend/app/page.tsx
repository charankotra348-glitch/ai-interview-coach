import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-6 px-4 text-center">
      <h1 className="text-4xl font-semibold">AI Interview Coach</h1>
      <p className="max-w-md opacity-80">
        Practice behavioral, project and system design interviews built from your own resume,
        with rubric-based feedback and follow-up questions.
      </p>
      <div className="flex gap-3">
        <Link href="/login" className="rounded-md bg-foreground px-4 py-2 font-medium text-background">Log in</Link>
        <Link href="/register" className="rounded-md border border-black/15 px-4 py-2 dark:border-white/20">Create account</Link>
      </div>
    </main>
  );
}