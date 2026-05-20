"use client";

import { useEffect, useState } from "react";
import Output from "./output";
import CallForm from "./CallForm";

export default function Home() {
  const [ws, setWs] = useState<WebSocket>();
  const [answer, setAnswer] = useState("");

  useEffect(() => {
    const websocket = new WebSocket("ws://localhost:8080");
    setWs(websocket);

    websocket.onopen = () => {
      console.log("Connection established");
    };

    websocket.onmessage = (event) => {
      setAnswer(event.data);
    };

    websocket.onclose = () => {
      setAnswer("");
    };

    return () => {
      websocket.close();
    };
  }, []);

  function sendInformation(formData: FormData) {
    setAnswer(
      `AI Response: This is a fake AI-generated answer for testing the frontend UI.`,
    );
    
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          phone: formData.get("phoneNumber"),
          link: formData.get("link"),
          questions: formData.get("questions"),
        }),
      );
    }
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
