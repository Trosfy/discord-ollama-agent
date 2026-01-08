/**
 * MessageContent Component
 *
 * Renders message content with markdown, code blocks, and LaTeX.
 * Matches Open WebUI styling.
 */

"use client";

import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeRaw from "rehype-raw";
import { Button } from "@/components/ui/button";
import { Check, Copy } from "lucide-react";
import "katex/dist/katex.min.css";

interface MessageContentProps {
  content: string;
  role: "user" | "assistant" | "system";
}

export function MessageContent({ content, role }: MessageContentProps) {
  // Helper to extract text from React children
  const getTextContent = (children: React.ReactNode): string => {
    if (typeof children === 'string') return children;
    if (typeof children === 'number') return String(children);
    if (Array.isArray(children)) return children.map(getTextContent).join('');
    if (children && typeof children === 'object' && 'props' in children) {
      const element = children as any;
      return getTextContent(element.props?.children);
    }
    return '';
  };

  return (
    <div className="prose prose-slate dark:prose-invert prose-pre:p-0 prose-pre:bg-transparent max-w-none overflow-hidden break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight, rehypeRaw]}
        components={{
          // Custom code block rendering
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const language = match ? match[1] : "";
            const isInline = !match;

            if (!isInline && language) {
              const codeContent = getTextContent(children).replace(/\n$/, "");
              return (
                <CodeBlock language={language}>
                  {codeContent}
                </CodeBlock>
              );
            }

            // Inline code
            return (
              <code
                className="bg-slate-800 text-slate-100 px-1.5 py-0.5 rounded text-sm font-mono break-all"
                {...props}
              >
                {children}
              </code>
            );
          },

          // Pre blocks (code without language)
          pre({ node, children, ...props }) {
            return (
              <pre className="overflow-x-auto max-w-full bg-slate-900 p-4 rounded-lg" {...props}>
                {children}
              </pre>
            );
          },

          // Links
          a({ node, children, href, ...props }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500 hover:text-blue-400 underline"
                {...props}
              >
                {children}
              </a>
            );
          },

          // Lists
          ul({ node, children, ...props }) {
            return (
              <ul className="list-disc list-inside space-y-1" {...props}>
                {children}
              </ul>
            );
          },

          ol({ node, children, ...props }) {
            return (
              <ol className="list-decimal list-inside space-y-1" {...props}>
                {children}
              </ol>
            );
          },

          // Tables
          table({ node, children, ...props }) {
            return (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse border border-slate-700" {...props}>
                  {children}
                </table>
              </div>
            );
          },

          th({ node, children, ...props }) {
            return (
              <th
                className="border border-slate-700 bg-slate-800 px-4 py-2 text-left font-semibold"
                {...props}
              >
                {children}
              </th>
            );
          },

          td({ node, children, ...props }) {
            return (
              <td className="border border-slate-700 px-4 py-2" {...props}>
                {children}
              </td>
            );
          },

          // Blockquotes
          blockquote({ node, children, ...props }) {
            return (
              <blockquote
                className="border-l-4 border-blue-500 pl-4 italic text-slate-400"
                {...props}
              >
                {children}
              </blockquote>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

/**
 * CodeBlock Component
 *
 * Syntax-highlighted code block with copy button
 */
function CodeBlock({ language, children }: { language: string; children: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(children);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div className="relative group my-4 max-w-full overflow-hidden rounded-lg">
      {/* Language label and copy button */}
      <div className="flex items-center justify-between bg-slate-900 px-4 py-2 border-b border-slate-700">
        <span className="text-xs text-slate-400 font-mono uppercase">{language}</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-slate-400 hover:text-slate-100 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={handleCopy}
        >
          {copied ? (
            <>
              <Check className="h-3 w-3 mr-1" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3 w-3 mr-1" />
              Copy
            </>
          )}
        </Button>
      </div>

      {/* Code content */}
      <pre className="!mt-0 bg-slate-900 overflow-x-auto p-4">
        <code className={`language-${language} text-sm`}>{children}</code>
      </pre>
    </div>
  );
}
