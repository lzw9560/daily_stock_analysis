import type React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { cn } from '../../utils/cn';

export type TabDef = {
  key: string;
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
};

type TabLayoutProps = {
  tabs: TabDef[];
  ariaLabel: string;
  /** 内容区的额外 className */
  className?: string;
};

export const TabLayout: React.FC<TabLayoutProps> = ({ tabs, ariaLabel, className }) => {
  return (
    <div className="flex flex-col">
      <nav
        className="sticky top-16 z-20 -mx-3 border-b border-border/60 bg-background/90 backdrop-blur-xl sm:-mx-4 lg:-mx-0"
        aria-label={ariaLabel}
      >
        <div className="flex gap-0 overflow-x-auto px-3 sm:px-4 lg:px-0 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
          {tabs.map((tab) => (
            <NavLink
              key={tab.key}
              to={tab.to}
              end
              className={({ isActive }: { isActive: boolean }) =>
                cn(
                  'group relative flex shrink-0 items-center gap-1.5 whitespace-nowrap px-3 py-2.5 text-sm font-medium transition-colors',
                  'border-b-2 -mb-[1px]',
                  isActive
                    ? 'border-primary text-primary'
                    : 'border-transparent text-secondary-text hover:text-foreground hover:border-border/60'
                )
              }
            >
              {({ isActive }: { isActive: boolean }) => (
                <>
                  <tab.icon className={cn('h-3.5 w-3.5 shrink-0', isActive ? 'text-primary' : 'text-current opacity-60')} />
                  <span>{tab.label}</span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
      <div className={cn('pt-4', className)}>
        <Outlet />
      </div>
    </div>
  );
};
