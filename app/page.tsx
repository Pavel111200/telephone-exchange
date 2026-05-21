"use client";

import { useState } from "react";
import Output from "./output";
import CallForm from "./CallForm";

export default function Home() {
  const [answer, setAnswer] = useState("");

  function sendInformation(formData: FormData) {
    //Set params
    const params = new URLSearchParams({
      phoneNumber: String(formData.get("phoneNumber") ?? ""),
      link: String(formData.get("link") ?? ""),
      questions: String(formData.get("questions") ?? ""),
    });

    //Send req
    const events = new EventSource(`/api/call_bot?${params}`);

    //handle start
    events.addEventListener("start", (event) => {
      const data = JSON.parse(event.data);
      setAnswer((current) => current + data.message + "\n");
    });

    //handle logs
    events.addEventListener("log", (event) => {
      const data = JSON.parse(event.data);
      setAnswer((current) => current + data.message);
    });

    //handle the returned result => JSON
    events.addEventListener("result", (event) => {
      const result = JSON.parse(event.data);
      setAnswer((current) => current + "\n\nFinal result:\n" + JSON.stringify(result, null, 2));
    });

    //Handle finish
    events.addEventListener("done", () => {
      events.close();
    });

    //handle validation error
    events.addEventListener("validation-error", (event) => {
      const data = JSON.parse(event.data);
      setAnswer((current) => current + "\n" + data.message + "\n");
      events.close();
    });

    //Handle general errors
    events.addEventListener("error", (event) => {
      setAnswer((current) => current + "\nBackend stream error\n");
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
