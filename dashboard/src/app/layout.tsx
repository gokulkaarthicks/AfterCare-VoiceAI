import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { DashboardShell } from "@/components/aftercare/dashboard-shell";
import { DoctorProvider } from "@/lib/doctor-context";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AfterCare - Voice AI",
  description: "Multi-agent healthcare follow-up system",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen antialiased`}>
        <DoctorProvider>
          <DashboardShell>{children}</DashboardShell>
        </DoctorProvider>
      </body>
    </html>
  );
}
