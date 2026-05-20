import { spawn } from "node:child_process";
import path from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Server-Sent Events require this exact text format.
function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  // Keep the HTTP response open so logs can be pushed as they arrive.
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      const botDir = path.join(process.cwd(), "app", "api", "python_call_bot");
      const pythonPath =
        process.platform === "win32"
          ? path.join(botDir, ".venv", "Scripts", "python.exe")
          : path.join(botDir, ".venv", "bin", "python");
      const scriptPath = path.join(botDir, "main.py");

      // Prevent writes after the browser disconnects or the process exits.
      let closed = false;

      const send = (event: string, data: unknown) => {
        if (!closed) {
          controller.enqueue(encoder.encode(sse(event, data)));
        }
      };

      const close = () => {
        if (!closed) {
          closed = true;
          controller.close();
        }
      };

      // -u and PYTHONUNBUFFERED make Python logs stream immediately.
      const child = spawn(pythonPath, ["-u", scriptPath], {
        cwd: botDir,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: "1",
          PYTHONIOENCODING: "utf-8",
          PYTHONUTF8: "1",
        },
      });

      // Stop the Python process if the frontend closes the SSE connection.
      request.signal.addEventListener("abort", () => {
        child.kill();
        close();
      });

      send("start", { message: "Call bot started" });

      // Build the final response
      let stdoutBuffer = "";
      child.stdout.on("data", (data: Buffer) => {
        stdoutBuffer += data.toString();
      });

      //Send the logs
      child.stderr.on("data", (data: Buffer) => {
        send("log", { stream: "stderr", message: data.toString() });
      });

      //Send the errors
      child.on("error", (error) => {
        send("error", { message: error.message });
        close();
      });

      //Send the final response
      child.on("close", (code) => {
        const output = stdoutBuffer.trim();

        if (output) {
          try {
            send("result", JSON.parse(output));
          } catch {
            send("log", { stream: "stdout", message: output });
          }
        }

        send("done", { code });
        close();
      });
    },
  });

  // These headers tell the browser/proxies to keep the SSE stream live.
  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
