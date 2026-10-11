import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import privacy from "../../../PRIVACY.md?raw";
import terms from "../../../TERMS.md?raw";
import { Footer, Nav } from "./Layout";
import "./styles.css";
import { applyStoredTheme } from "./theme";

applyStoredTheme();

/** Inline markdown: **bold**, `code`, [links](url). */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*(.+?)\*\*|`(.+?)`|\[(.+?)\]\((.+?)\)|_(.+?)_|<(https?:\/\/[^>]+)>/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(<strong key={k++}>{m[1]}</strong>);
    else if (m[2]) out.push(<code key={k++} className="rounded bg-[var(--panel)] px-1.5 py-0.5 text-[0.88em]">{m[2]}</code>);
    else if (m[3]) {
      const href = m[4]!.startsWith("http") ? m[4]! : `https://github.com/RavirajSarangan/agentsasu/blob/main/${m[4]}`;
      out.push(<a key={k++} href={href} className="font-medium text-[var(--accent)] underline-offset-4 hover:underline">{m[3]}</a>);
    } else if (m[5]) out.push(<em key={k++}>{m[5]}</em>);
    else if (m[6]) out.push(<a key={k++} href={m[6]} className="font-medium text-[var(--accent)] underline-offset-4 hover:underline">{m[6]}</a>);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Just enough markdown for our own policy files: headings, paragraphs, lists, tables. */
function Markdown({ src }: { src: string }) {
  const blocks = src.trim().split(/\n{2,}/);
  return (
    <>
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        if (b.startsWith("# ")) return <h1 key={i} className="display text-[clamp(2.4rem,6vw,4rem)]">{b.slice(2)}</h1>;
        if (b.startsWith("## ")) return <h2 key={i} className="title mt-10 text-[1.6rem]">{b.slice(3)}</h2>;
        if (lines.every((l) => l.startsWith("|"))) {
          const rows = lines.filter((l) => !/^\|\s*-/.test(l)).map((l) => l.split("|").slice(1, -1).map((c) => c.trim()));
          return (
            <div key={i} className="mt-5 overflow-x-auto rounded-2xl border border-[var(--line)]">
              <table className="w-full min-w-[560px] text-left text-[0.95rem]">
                <thead className="bg-[var(--bg-2)]">
                  <tr>{rows[0]!.map((c, j) => <th key={j} className="px-4 py-3 font-semibold">{inline(c)}</th>)}</tr>
                </thead>
                <tbody>
                  {rows.slice(1).map((r, ri) => (
                    <tr key={ri} className="border-t border-[var(--line)]">{r.map((c, j) => <td key={j} className="px-4 py-3 align-top text-[var(--muted)]">{inline(c)}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        if (/^(\d+\.|-) /.test(lines[0]!)) {
          const items = b.split(/\n(?=\d+\. |- )/).map((l) => l.replace(/^(\d+\.|-) /, "").replace(/\n\s+/g, " "));
          const ordered = /^\d+\./.test(lines[0]!);
          const Tag = ordered ? "ol" : "ul";
          return (
            <Tag key={i} className={`mt-4 flex flex-col gap-2 pl-6 text-[var(--muted)] ${ordered ? "list-decimal" : "list-disc"}`}>
              {items.map((it, j) => <li key={j} className="leading-relaxed">{inline(it)}</li>)}
            </Tag>
          );
        }
        return <p key={i} className="mt-4 max-w-[68ch] leading-relaxed text-[var(--muted)]">{inline(b.replace(/\n/g, " "))}</p>;
      })}
    </>
  );
}

const page = location.pathname.includes("terms") ? terms : privacy;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Nav home="" />
    <main className="px-4 pb-24 pt-32 sm:px-6">
      <article className="mx-auto max-w-[820px]">
        <Markdown src={page} />
      </article>
    </main>
    <Footer />
  </StrictMode>,
);
