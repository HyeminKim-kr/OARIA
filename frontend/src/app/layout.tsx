import type { Metadata } from "next";
import { Outfit, DM_Sans } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/contexts/AuthContext";
import { NotificationProvider } from "@/contexts/NotificationContext";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ToastContainer } from "@/components/notifications";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "OARIA - Research Intelligence",
  description: "AI-powered cancer research assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${outfit.variable} ${dmSans.variable} antialiased`}
      >
        <AuthProvider>
          <NotificationProvider>
            <QueryProvider>{children}</QueryProvider>
            <ToastContainer />
          </NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
