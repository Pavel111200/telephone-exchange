"use client";

import { useEffect, useState } from "react";

const [ws, setWs] = useState<WebSocket>();

useEffect(() => {
  const websocket = new WebSocket("ws://localhost:8080");
  setWs(websocket);

  websocket.onopen = () => {
    console.log("Connection established");
  };

  websocket.onmessage = (event) => {
    console.log(event.data);
  };
}, []);

function sendInformation(formData: FormData) {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        phone: formData.get("phone"),
        link: formData.get("link"),
        questions: formData.get("questions"),
      }),
    );
  }
}

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-center py-32 px-16">
        <form
          action={sendInformation}
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
      </main>
    </div>
  );
}
