import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { SidebarNav } from '../SidebarNav';

vi.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    authEnabled: true,
    logout: vi.fn(),
  }),
}));

vi.mock('../../../stores/agentChatStore', () => ({
  useAgentChatStore: () => ({ completionBadge: false }),
}));

vi.mock('../../../api/alphasift', () => ({
  ALPHASIFT_CONFIG_CHANGED_EVENT: 'alphasift-config-changed',
  SYSTEM_CONFIG_CHANGED_EVENT: 'dsa-system-config-changed',
  alphasiftApi: {
    getStatus: () => Promise.resolve({ enabled: false, available: false, installSpecIsDefault: false }),
  },
}));

vi.mock('../../theme/ThemeToggle', () => ({
  ThemeToggle: () => null,
}));

describe('SidebarNav execution link', () => {
  it('renders the execution panel entry', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <SidebarNav />
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: '执行面板' })).toHaveAttribute('href', '/execution');
  });
});
