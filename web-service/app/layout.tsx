import type { Metadata, Viewport } from "next";
import { Poppins, Saira } from "next/font/google";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import "./globals.css";
import "highlight.js/styles/atom-one-dark.css";

// Poppins font - Body text
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-sans",
  display: "swap",
});

// Saira font - Headings
const saira = Saira({
  subsets: ["latin"],
  weight: ["100", "200", "300", "400", "500", "600", "700", "800", "900"],
  variable: "--font-heading",
  display: "swap",
});

// Viewport configuration for responsive mobile design
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  userScalable: true,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FEFBF3" },
    { media: "(prefers-color-scheme: dark)", color: "#191716" },
  ],
};

export const metadata: Metadata = {
  title: "Trollama - AI Agent Workspace",
  description: "Your intelligent AI agent workspace powered by advanced language models",
  keywords: ["AI", "Chat", "LLM", "Agent", "Trollama", "Open WebUI"],
  authors: [{ name: "Trollama Team" }],
  creator: "Trollama",
  publisher: "Trollama",
  applicationName: "Trollama Web",
  generator: "Next.js",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" },
      { url: "/favicon.ico", sizes: "32x32", type: "image/x-icon" },
    ],
    shortcut: "/favicon.svg",
    apple: "/apple-icon.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Trollama",
  },
  formatDetection: {
    telephone: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${poppins.variable} ${saira.variable} antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          themes={["light", "dark", "oled-dark", "rose-pine"]}
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
