import type React from 'react';
import { Component, useEffect, useState } from 'react';
import { Menu } from 'lucide-react';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'motion/react';
import { Drawer } from '../common/Drawer';
import { SidebarNav } from './SidebarNav';
import { cn } from '../../utils/cn';
import { ThemeToggle } from '../theme/ThemeToggle';

type ShellProps = {
  children?: React.ReactNode;
};

/** 捕获 SidebarNav 渲染错误，避免整个页面白屏 */
class SidebarErrorBoundary extends Component<{ children: React.ReactNode }, { hasError: boolean }> {
  override state = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  override render() {
    if (this.state.hasError) {
      return (
        <aside className="sticky top-3 z-40 hidden shrink-0 overflow-visible rounded-[1.5rem] border border-[var(--shell-sidebar-border)] bg-card/72 p-2 shadow-soft-card backdrop-blur-sm lg:flex w-[116px] max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]">
          <div className="flex h-full flex-col items-center justify-center gap-2 text-xs text-muted-text p-2">
            <span>导航加载失败</span>
          </div>
        </aside>
      );
    }
    return this.props.children;
  }
}

const pageTransition = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
  transition: { duration: 0.2, ease: 'easeOut' },
};

export const Shell: React.FC<ShellProps> = ({ children }) => {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const collapsed = false;

  useEffect(() => {
    if (!mobileOpen) {
      return undefined;
    }

    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileOpen(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [mobileOpen]);

  // Close mobile drawer on navigation
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Mobile header */}
      <div className="pointer-events-none fixed inset-x-0 top-3 z-40 flex items-start justify-between px-3 lg:hidden">
        <button
          type="button"
          onClick={() => setMobileOpen(true)}
          className="pointer-events-auto inline-flex h-10 w-10 items-center justify-center rounded-xl border border-border/70 bg-card/85 text-secondary-text shadow-soft-card backdrop-blur-md transition-colors hover:bg-hover hover:text-foreground"
          aria-label="打开导航菜单"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="pointer-events-auto">
          <ThemeToggle />
        </div>
      </div>

      <div className="mx-auto flex min-h-screen w-full max-w-[1680px] px-3 py-3 sm:px-4 sm:py-4 lg:px-5">
        {/* Desktop sidebar */}
        <aside
          className={cn(
            'sticky top-3 z-40 hidden shrink-0 overflow-visible rounded-[1.5rem] border border-[var(--shell-sidebar-border)] bg-card/72 p-2 shadow-soft-card backdrop-blur-sm transition-all duration-300 lg:flex',
            'max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]',
            collapsed ? 'w-[64px]' : 'w-[116px]'
          )}
          aria-label="桌面侧边导航"
        >
          <SidebarErrorBoundary>
            <SidebarNav collapsed={collapsed} onNavigate={() => setMobileOpen(false)} />
          </SidebarErrorBoundary>
        </aside>

        {/* Main content with page transitions */}
        <main className="min-h-0 min-w-0 flex-1 pt-14 lg:pl-3 lg:pt-0 touch-pan-y">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              {...pageTransition}
            >
              {children ?? <Outlet />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      {/* Mobile drawer */}
      <Drawer
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        title="导航菜单"
        width="max-w-xs"
        zIndex={90}
        side="left"
      >
        <SidebarNav onNavigate={() => setMobileOpen(false)} />
      </Drawer>
    </div>
  );
};
