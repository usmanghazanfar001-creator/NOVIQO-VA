import type { Status } from "../types";
export default function Orb({ status, onClick }: { status: Status; onClick: () => void }) {
  const label = { idle: "Start listening", listening: "Stop listening", thinking: "Thinking", speaking: "Stop speaking", error: "Try again" }[status];
  return <button aria-label={label} onClick={onClick} className={`orb orb-${status} focus-visible:outline-2 focus-visible:outline-secondary focus-visible:outline-offset-8`} />;
}
