import type React from 'react';
import { Component, useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Drawer } from '../common/Drawer';
import { ShellHeader } from './ShellHeader';
import { SidebarNav } from './SidebarNav';

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
        <aside
          className="sticky top-3 z-40 hidden shrink-0 overflow-visible rounded-[1.5rem] border border-[var(--shell-sidebar-border)] bg-card/72 p-2 shadow-soft-card backdrop-blur-sm lg:flex max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]"
          style={{ width: 'var(--shell-sidebar-width)' }}
        >
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
      <div className="mx-auto flex min-h-screen w-full max-w-[var(--shell-content-max-width)] px-3 py-3 sm:px-4 sm:py-4 lg:px-5">
        {/* Desktop sidebar — 固定展开 */}
        <aside
          className="sticky top-3 z-40 hidden shrink-0 overflow-visible rounded-[1.5rem] border border-[var(--shell-sidebar-border)] bg-card/72 p-2 shadow-soft-card backdrop-blur-sm lg:flex max-h-[calc(100vh-1.5rem)] self-start sm:top-4 sm:max-h-[calc(100vh-2rem)]"
          style={{ width: 'var(--shell-sidebar-width)' }}
          aria-label="桌面侧边导航"
        >
          <SidebarErrorBoundary>
            <SidebarNav collapsed={false} onNavigate={() => setMobileOpen(false)} />
          </SidebarErrorBoundary>
        </aside>

        {/* Main content with ShellHeader + page transitions */}
        <div className="min-h-0 min-w-0 flex-1 pt-14 lg:pl-3 lg:pt-0 touch-pan-y">
          <ShellHeader
            onOpenMobileNav={() => setMobileOpen(true)}
          />
          {/* 顶部标签栏 — 由嵌套 Layout 组件渲染 */}
          <main>
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
