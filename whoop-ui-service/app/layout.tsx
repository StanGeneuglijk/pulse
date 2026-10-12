import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import { BRAND } from "@/lib/brand";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: `${BRAND.name} — WHOOP + AI nutrition`,
  description: BRAND.tagline,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`}>
      <body className="relative font-sans text-white antialiased">
        {/* Slow-moving color glows behind the content. */}
        <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
          <div className="absolute -left-40 -top-40 h-[520px] w-[520px] animate-float rounded-full bg-strain/20 blur-[120px]" />
          <div
            className="absolute -right-32 top-20 h-[460px] w-[460px] animate-float rounded-full bg-fuel/15 blur-[120px]"
            style={{ animationDelay: "-5s" }}
          />
          <div
            className="absolute bottom-0 left-1/3 h-[420px] w-[420px] animate-float rounded-full bg-sleep/10 blur-[120px]"
            style={{ animationDelay: "-9s" }}
          />
        </div>
        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
