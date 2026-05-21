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
      const data = JSON.parse(event.data);

      const result = formatResult(data);
      setAnswer((current) => current + "\n\nFinal result:\n" + result);
    });

    events.addEventListener("error", (event) => {
      setAnswer((current) => current + "\nBackend stream error\n");
      events.close();
    });

    events.addEventListener("done", () => {
      events.close();
    });
  }

  function formatResult(data: any): string {
    const phoneNumber = data.phone_number;
    const jobPosition = data.job_posting.position;
    const company = data.job_posting.company;
    const link = data.job_posting.url;
    const result = data.summary;

    return `Кандидат: ${phoneNumber}
Позиция: ${jobPosition}
Работодател: ${company}
Линк към обявата: ${link}
Отговор на кандидата: ${result}`;
  }

  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-center py-32 px-16 gap-6">
        {!answer && <CallForm sendInformation={sendInformation} />}
        {answer && (
          <>
            <Output answer={answer} />
            <button className="text-black rounded-sm border border-black p-2" onClick={() => setAnswer("")}>
              New call
            </button>
          </>
        )}
      </main>
    </div>
  );
}
