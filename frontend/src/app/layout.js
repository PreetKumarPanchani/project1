import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: 'LiquidQube - AI Database Assistant',
  description: 'Voice-enabled AI database query assistant',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" />
      </head>
      <body className={inter.className}>
        {children}
      </body>
    </html>
  );
}