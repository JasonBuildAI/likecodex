import { describe, expect, it } from 'vitest';
import { parseRustEvent } from './api';

describe('parseRustEvent', () => {
  it('parses stream_chunk', () => {
    const parsed = parseRustEvent({
      type: 'stream_chunk',
      payload: { task_id: 't1', content: 'hello' },
    });
    expect(parsed.kind).toBe('stream_chunk');
    expect(parsed.content).toBe('hello');
  });

  it('parses task_completed failure', () => {
    const parsed = parseRustEvent({
      type: 'task_completed',
      payload: { id: 't1', status: 'failed' },
    });
    expect(parsed.kind).toBe('task_completed');
    expect(parsed.content).toBe('failed');
  });
});
