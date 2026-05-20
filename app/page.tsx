"use client";

import { useState } from "react";
import Output from "./output";
import CallForm from "./CallForm";

export default function Home() {
  const [answer, setAnswer] = useState("");

  function sendInformation(formData: FormData) {
    const events = new EventSource("/api/call_bot");

    events.addEventListener("start", (event) => {
      const data = JSON.parse(event.data);
      setAnswer((current) => current + data.message + "\n");
    });

    events.addEventListener("log", (event) => {
      const data = JSON.parse(event.data);
      setAnswer((current) => current + data.message);
    });

    events.addEventListener("result", (event) => {
      const result = JSON.parse(event.data);
      setAnswer((current) => current + "\n\nFinal result:\n" + JSON.stringify(result, null, 2));
    });

    events.addEventListener("error", (event) => {
      setAnswer((current) => current + "\nBackend stream error\n");
      events.close();
    });

    events.addEventListener("done", () => {
      events.close();
    });
  }

  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-center py-32 px-16 gap-6">
        <CallForm sendInformation={sendInformation} />
        {answer && <Output answer={answer} />}
      </main>
    </div>
  );
}
