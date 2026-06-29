import type React from 'react';
import { useEffect } from 'react';
import { ThemeProvider as NextThemesProvider } from 'next-themes';
import { useTheme } from 'next-themes';

type ThemeProviderProps = {
  children: React.ReactNode;
};

const THEMES = ['light', 'dark', 'blue-dark', 'orange', 'orange-dark'] as const;
type ThemeValue = (typeof THEMES)[number];

const ThemeClassSetter: React.FC = () => {
  const { theme } = useTheme();
  useEffect(() => {
    const html = document.documentElement;
    html.classList.remove('light', 'dark', 'blue-dark', 'orange', 'orange-dark');
    const active = (theme ?? 'dark') as ThemeValue;
    if (THEMES.includes(active)) {
      html.classList.add(active);
    }
  }, [theme]);
  return null;
};

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
      themes={['light', 'dark', 'blue-dark', 'orange', 'orange-dark']}
    >
      <ThemeClassSetter />
      {children}
    </NextThemesProvider>
  );
};
