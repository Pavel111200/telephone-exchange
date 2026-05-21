import { spawn } from "node:child_process";
import path from "node:path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

// Server-Sent Events require this exact text format.
function sse(event: string, data: unknown) {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function getErrorResponse(responseType: string, msg: string, encoder: TextEncoder) {
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(
        encoder.encode(sse(responseType, { message: msg }))
      );
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}

export async function GET(request: Request) {
  const encoder = new TextEncoder();

  //Get the req params
  const searchParams = new URL(request.url).searchParams;
  const phoneNumber = searchParams.get("phoneNumber") ?? "";
  const jobLink = searchParams.get("link") ?? "";
  const questions = searchParams.get("questions") ?? "";

  //Validation - Phone and link are reqired
  if (!phoneNumber || !jobLink) {
    return getErrorResponse("validation-error", "Phone number and link are required", encoder);
  }

  //Get possition and title from link
  const apiUrl = new URL("https://bg.jobee.bg/api/callcenter_calls.php");
  apiUrl.searchParams.set("link", jobLink);
  const res = await fetch(apiUrl.toString());
  const data = await res.json();

  //Validate that link is real
  if (data.status == "not_found") {
    return getErrorResponse("validation-error", "Job posting wasn't found", encoder);
  }

  //Extract data
  const jobTitle = data.position_title;
  const jobCompany = data.company;

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

      // start the python bot with the passed parameters
      // -u and PYTHONUNBUFFERED make Python logs stream immediately.
      const child = spawn(
        pythonPath,
        ["-u", scriptPath, "--phone", phoneNumber, "--job-link", jobLink, "--job-title", jobTitle, "--job-company", jobCompany , "--questions", questions],
        {
          cwd: botDir,
          env: {
            ...process.env,
            PYTHONUNBUFFERED: "1",
            PYTHONIOENCODING: "utf-8",
            PYTHONUTF8: "1",
          },
        }
      );

      // Stop the Python process if the frontend closes the SSE connection.
      request.signal.addEventListener("abort", () => {
        child.kill();
        close();
      });

      send("start", {
        message: `Call bot started: Phone number: ${phoneNumber}, Link: ${jobLink}, Questions: ${questions}`
      });

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
