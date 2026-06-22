import { describe, expect, it } from 'vitest';
import FactorPipelineSummaryCard from '../FactorPipelineSummaryCard';

describe('FactorPipelineSummaryCard', () => {
  it('exports a renderable component', () => {
    expect(typeof FactorPipelineSummaryCard).toBe('function');
  });
});
