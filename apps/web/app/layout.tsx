import type { Metadata } from "next";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./globals.css";
import { Providers } from "./providers";
import { DOCMIND_ICON_32, DOCMIND_ICON_512, PRODUCT_NAME } from "@/lib/brand";

export const metadata: Metadata = {
  applicationName: PRODUCT_NAME,
  title: { default: PRODUCT_NAME, template: `%s · ${PRODUCT_NAME}` },
  description: "AI document workspace with grounded answers and source citations",
  icons: {
    icon: [
      { url: DOCMIND_ICON_32, sizes: "32x32", type: "image/png" },
      { url: DOCMIND_ICON_512, sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: DOCMIND_ICON_512, sizes: "512x512", type: "image/png" }],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
