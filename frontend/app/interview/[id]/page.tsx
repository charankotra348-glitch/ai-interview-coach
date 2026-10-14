import Link from "next/link";

// The interview screen arrives in Step 8c. This placeholder keeps the link from the dashboard working.
export default function InterviewPage() {
  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-16">
      <h1 className="text-2xl font-semibold">Your interview is ready</h1>
      <p className="mt-2 text-pencil">The question-and-answer screen is the next part of the build.</p>
      <Link href="/dashboard" className="mt-6 inline-block underline">Back to the dashboard</Link>
    </main>
  );
}