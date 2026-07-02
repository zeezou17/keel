/**
 * Renders sparring assistant replies as Markdown (React elements, not raw HTML).
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const markdownComponents: Components = {
  h1: ({ children }) => <h3 className="spar-md-h3">{children}</h3>,
  h2: ({ children }) => <h3 className="spar-md-h3">{children}</h3>,
  h3: ({ children }) => <h4 className="spar-md-h4">{children}</h4>,
  h4: ({ children }) => <h4 className="spar-md-h4">{children}</h4>,
  p: ({ children }) => <p className="spar-md-p">{children}</p>,
  ul: ({ children }) => <ul className="spar-md-ul">{children}</ul>,
  ol: ({ children }) => <ol className="spar-md-ol">{children}</ol>,
  li: ({ children }) => <li className="spar-md-li">{children}</li>,
  strong: ({ children }) => <strong className="spar-md-strong">{children}</strong>,
  code: ({ children }) => <code className="spar-md-code">{children}</code>,
};

interface SparMessageContentProps {
  content: string;
}

export function SparMessageContent({ content }: SparMessageContentProps) {
  return (
    <div className="spar-message-body spar-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
