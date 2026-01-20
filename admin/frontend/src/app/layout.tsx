import type { Metadata } from 'next';
import './globals.css';
import { Providers } from './providers';
import { AuthLayout } from '@/components/layout/AuthLayout';

export const metadata: Metadata = {
  title: 'OARIA Admin',
  description: 'Cancer Paper Collection Service Admin',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased">
        <Providers>
          <AuthLayout>{children}</AuthLayout>
        </Providers>
      </body>
    </html>
  );
}
