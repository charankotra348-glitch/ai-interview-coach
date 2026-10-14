import { Suspense } from "react";
import { SummaryScreen } from "@/components/summary-screen";

// The screen reads the interview id from the URL, which is only known at request time.
// With Cache Components that read must sit inside a Suspense boundary.
export default function Page() {
  return (
    <Suspense fallback={<p className="mx-auto w-full max-w-3xl px-4 py-16 text-pencil">Loading your summary...</p>}>
      <SummaryScreen />
    </Suspense>
  );
}