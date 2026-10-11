// Intruder selfie (opt-in): when the core asks, grab ONE camera frame and upload it.
// The camera is opened only for that moment and stopped right after.
import { apiFetch } from "../agent/connection";
import { onAgentEvent } from "../agent/store";
import { settingsStore } from "./settings";

async function grabJpeg(): Promise<Blob | null> {
  if (!navigator.mediaDevices?.getUserMedia) return null;
  let stream: MediaStream | null = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    await video.play();
    await new Promise((r) => setTimeout(r, 600)); // let exposure settle
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    return await new Promise((r) => canvas.toBlob((b) => r(b), "image/jpeg", 0.8));
  } catch {
    return null;
  } finally {
    stream?.getTracks().forEach((t) => t.stop());
  }
}

let started = false;
export function startSnapListener() {
  if (started) return;
  started = true;
  onAgentEvent((e) => {
    if (e.type !== "snap_request" || !settingsStore.get().intruderPhoto) return;
    void grabJpeg().then((jpeg) => {
      if (jpeg) void apiFetch(`/api/intruders?snap=${encodeURIComponent(e.id)}`, { method: "POST", body: jpeg });
    });
  });
}
