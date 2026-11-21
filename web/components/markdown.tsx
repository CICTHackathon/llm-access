import * as React from "react"

// A small renderer for what the assistant writes: paragraphs, "- " lists,
// **bold**, *italic* / _italic_ and `code`. Text is never inserted as HTML.

function inline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*|_[^_]+_)/g
  let last = 0
  let match: RegExpExecArray | null
  while ((match = pattern.exec(text))) {
    if (match.index > last) parts.push(text.slice(last, match.index))
    const token = match[0]
    const key = `${match.index}-${token}`
    if (token.startsWith("**")) parts.push(<strong key={key}>{token.slice(2, -2)}</strong>)
    else if (token.startsWith("`")) parts.push(<code key={key} className="rounded bg-muted px-1 text-[0.85em]">{token.slice(1, -1)}</code>)
    else parts.push(<em key={key}>{token.slice(1, -1)}</em>)
    last = match.index + token.length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}

export function Markdown({ text }: { text: string }) {
  const blocks = text.replace(/\r\n/g, "\n").split(/\n{2,}/)
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      {blocks.map((block, i) => {
        const lines = block.split("\n")
        if (lines.every((l) => /^\s*[-*] /.test(l))) {
          return (
            <ul key={i} className="list-disc space-y-0.5 pl-5">
              {lines.map((l, j) => (
                <li key={j}>{inline(l.replace(/^\s*[-*] /, ""))}</li>
              ))}
            </ul>
          )
        }
        return (
          <p key={i}>
            {lines.map((l, j) => (
              <React.Fragment key={j}>
                {j > 0 && <br />}
                {/^\s*[-*] /.test(l) ? <>&bull; {inline(l.replace(/^\s*[-*] /, ""))}</> : inline(l)}
              </React.Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
