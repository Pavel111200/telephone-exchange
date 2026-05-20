"use client";

import { useEffect, useState } from "react";
import Output from "./output";

export default function Home() {
  const [ws, setWs] = useState<WebSocket>();
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    // WEBSOCKET CONNECTION

    /*
    const websocket = new WebSocket("ws://localhost:8080");
    setWs(websocket);

    websocket.onopen = () => {
      console.log("Connection established");
    };

    websocket.onmessage = (event) => {
      console.log(event.data);
      setAnswer(event.data);
    };

    return () => {
      websocket.close();
    };
    */
  }, []);

  function sendInformation(formData: FormData) {
    setAnswer("");

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
        <form
          onSubmit={(event) => {
            event.preventDefault();
            sendInformation(new FormData(event.currentTarget));
          }}
          className="flex flex-col bg-black p-4 gap-4 rounded-md w-4/5"
        >
          <div className="flex flex-col">
            <label htmlFor="phone-number" className="text-white">
              Phone number
            </label>

            <input
              type="text"
              id="phone-number"
              name="phoneNumber"
              className="bg-white text-black rounded-xs h-7"
            />
          </div>

          <div className="flex flex-col">
            <label htmlFor="link" className="text-white">
              Link to job posting
            </label>

            <input
              type="text"
              id="link"
              name="link"
              className="bg-white text-black rounded-xs h-7"
            />
          </div>

          <div className="flex flex-col">
            <label htmlFor="questions" className="text-white">
              Questions
            </label>

            <textarea
              id="questions"
              name="questions"
              rows={4}
              className="bg-white text-black rounded-xs"
            ></textarea>
          </div>

          <button
            type="submit"
            className="w-fit self-end px-5 py-2 bg-white text-black rounded-sm"
          >
            Submit
          </button>
        </form>

        {answer && <Output answer={answer} />}
      </main>
    </div>
  );
}