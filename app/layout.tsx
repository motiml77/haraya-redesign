import type {Metadata} from 'next';
import { Frank_Ruhl_Libre, Assistant } from 'next/font/google';
import { NavigationProgress } from '@/components/NavigationProgress';
import './globals.css'; // Global styles

const frankRuhlLibre = Frank_Ruhl_Libre({
  subsets: ['hebrew', 'latin'],
  variable: '--font-serif',
});

const assistant = Assistant({
  subsets: ['hebrew', 'latin'],
  variable: '--font-sans',
});

export const metadata: Metadata = {
  title: "Commentaries on Rabbi Kook's Teachings",
  description: "A web application to display paragraphs from Rabbi Kook's books alongside detailed commentaries, sources, and user discussions.",
};

export default function RootLayout({children}: {children: React.ReactNode}) {
  return (
    <html lang="he" dir="rtl" className={`${frankRuhlLibre.variable} ${assistant.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var els = document.querySelectorAll('[data-modesty]');
                  for (var i = 0; i < els.length; i++) {
                    els[i].removeAttribute('data-modesty');
                  }
                  var observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                      if (mutation.type === 'attributes' && mutation.attributeName === 'data-modesty') {
                        mutation.target.removeAttribute('data-modesty');
                      }
                    });
                  });
                  observer.observe(document.documentElement, {
                    attributes: true,
                    subtree: true,
                    attributeFilter: ['data-modesty']
                  });
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="font-sans bg-[#FAF8F5] text-[#2C2A29] antialiased" suppressHydrationWarning><NavigationProgress />{children}</body>
    </html>
  );
}
