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
  title: "שיעורים בכתבי הרב קוק",
  description: "ביאורים והרחבות על כתבי מרן הרב אברהם יצחק הכהן קוק זצ״ל",
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
      <body className="font-sans bg-[#F1E6D2] text-[#1F1A14] antialiased" suppressHydrationWarning><NavigationProgress />{children}</body>
    </html>
  );
}
