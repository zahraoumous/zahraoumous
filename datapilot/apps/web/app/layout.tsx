import type { Metadata } from "next";
import "./globals.css";
import { PreferencesProvider } from "./lib/i18n";

export const metadata: Metadata = { title: "DataPilot AI", description: "Transparent data analysis" };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><body><PreferencesProvider>{children}</PreferencesProvider></body></html>;
}
