import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'LikeCodex',
  description: 'A production-grade Codex-like coding agent',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="antialiased min-h-screen bg-background text-foreground">
        {children}
      </body>
    </html>
  );
}
