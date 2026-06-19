import { describe, expect, it } from 'vitest';
import { formatRetryMessage, parseRustEvent } from './api';
import { useAppStore } from './store';

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

  it('parses partial tool dispatch', () => {
    const parsed = parseRustEvent({
      type: 'tool_call_requested',
      payload: {
        task_id: 't1',
        call: { id: 'c1', name: 'read_file', arguments: { partial: true } },
      },
    });
    expect(parsed.kind).toBe('tool_call');
    expect(parsed.call?.name).toBe('read_file');
    expect(parsed.call?.arguments?.partial).toBe(true);
  });

  it('parses stream_retrying with reason', () => {
    const parsed = parseRustEvent({
      type: 'stream_retrying',
      payload: {
        task_id: 't1',
        attempt: 2,
        max: 3,
        reason: 'provider',
        message: 'recover',
      },
    });
    expect(parsed.kind).toBe('retrying');
    expect(parsed.retryAttempt).toBe(2);
    expect(parsed.retryMax).toBe(3);
    expect(parsed.retryReason).toBe('provider');
  });

  it('parses compaction_started', () => {
    const parsed = parseRustEvent({
      type: 'compaction_started',
      payload: { task_id: 't1', trigger: 'token_limit' },
    });
    expect(parsed.kind).toBe('compaction_started');
    expect(parsed.content).toBe('token_limit');
  });

  it('parses compaction_done', () => {
    const parsed = parseRustEvent({
      type: 'compaction_done',
      payload: { task_id: 't1', archive: '/tmp/archive.json', messages: 12 },
    });
    expect(parsed.kind).toBe('compaction_done');
    expect(parsed.content).toBe('/tmp/archive.json');
  });

  it('parses checkpoint_created', () => {
    const parsed = parseRustEvent({
      type: 'checkpoint_created',
      payload: {
        task_id: 't1',
        checkpoint_id: 'cp1',
        label: 'write_file',
        files: ['a.txt', 'b.txt'],
      },
    });
    expect(parsed.kind).toBe('checkpoint_created');
    expect(parsed.content).toBe('cp1');
    expect(parsed.checkpointLabel).toBe('write_file');
    expect(parsed.checkpointFiles).toEqual(['a.txt', 'b.txt']);
  });

  it('parses permission_requested from content json', () => {
    const parsed = parseRustEvent({
      type: 'permission_requested',
      payload: {
        task_id: 't1',
        request: {
          id: 'req-1',
          action_type: 'write_file',
          description:
            '{"request_id":"req-1","tool":"write_file","arguments":{"path":"a.txt"},"reason":"ask"}',
        },
      },
    });
    expect(parsed.kind).toBe('permission');
    expect(parsed.permission?.requestId).toBe('req-1');
    expect(parsed.permission?.tool).toBe('write_file');
    expect(parsed.permission?.arguments?.path).toBe('a.txt');
  });

  it('parses permission_responded', () => {
    const parsed = parseRustEvent({
      type: 'permission_responded',
      payload: { task_id: 't1', request_id: 'req-1', response: 'allow_once' },
    });
    expect(parsed.kind).toBe('permission_responded');
    expect(parsed.permission?.requestId).toBe('req-1');
    expect(parsed.permission?.description).toBe('approved');
  });

  it('formats retry labels by reason', () => {
    expect(formatRetryMessage('provider', 1, 3)).toContain('Provider reconnect');
    expect(formatRetryMessage('stream_recovery', 2, 3)).toContain('Stream interrupted');
  });
});

describe('upsertToolDispatch', () => {
  it('merges partial dispatch into full tool call card', () => {
    useAppStore.setState({ messages: [] });
    const { upsertToolDispatch } = useAppStore.getState();
    upsertToolDispatch({ id: 'c1', name: 'read_file', arguments: { partial: true } }, true);
    upsertToolDispatch({ id: 'c1', name: 'read_file', arguments: { path: 'a.txt' } }, false);
    const messages = useAppStore.getState().messages;
    expect(messages).toHaveLength(1);
    expect(messages[0].eventType).toBe('tool_call');
    expect(messages[0].content).toContain('read_file');
    expect(messages[0].toolCalls?.[0].arguments.path).toBe('a.txt');
  });
});
