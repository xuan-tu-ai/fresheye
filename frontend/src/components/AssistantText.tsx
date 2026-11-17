import type { ReactNode } from "react";

/** Turns `*italic*` spans into <em>; used on the text between bold spans. */
function italics(text: string, key: number): ReactNode[] {
  return text
    .split(/\*([^*]+)\*/)
    .map((part, index) => (index % 2 === 1 ? <em key={`${key}-${index}`}>{part}</em> : part));
}

/** Turns `**bold**` spans into <strong> and `*italic*` spans into <em>; the rest stays plain text. */
function inline(text: string): ReactNode[] {
  return text
    .split("**")
    .flatMap((part, index): ReactNode[] =>
      index % 2 === 1 ? [<strong key={index}>{part}</strong>] : italics(part, index),
    );
}

/**
 * Renders the assistant's reply. The model writes light Markdown (bold, "- " lists, blank lines
 * between paragraphs, italics); only those are understood, and nothing is ever treated as HTML.
 */
export function AssistantText({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let bullets: string[] = [];

  const flush = () => {
    if (bullets.length === 0) return;
    blocks.push(
      <ul key={blocks.length} className="grid list-disc gap-1 pl-5">
        {bullets.map((item, index) => (
          <li key={index}>{inline(item)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const line of text.split("\n")) {
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    if (bullet) {
      bullets.push(bullet[1]);
      continue;
    }
    flush();
    if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>);
  }
  flush();

  return <div className="grid gap-2">{blocks}</div>;
}
