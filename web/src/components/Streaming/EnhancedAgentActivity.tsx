'use client';

import React, { memo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message, ToolCall } from '@/lib/store';
import { fadeInUp, staggerContainer, staggerItem } from '@/lib/animations';

// ── Tool metadata ────────────────────────────────────────────────────────
const TOOL_META: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  read_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
    label: 'Read', color: 'text-blue-400',
  },
  write_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>,
    label: 'Write', color: 'text-green-400',
  },
  edit_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>,
    label: 'Edit', color: 'text-green-400',
  },
  replace_in_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>,
    label: 'Replace', color: 'text-green-400',
  },
  run_command: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z" /></svg>,
    label: 'Run', color: 'text-amber-400',
  },
  execute_command: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z" /></svg>,
    label: 'Execute', color: 'text-amber-400',
  },
  shell: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z" /></svg>,
    label: 'Shell', color: 'text-amber-400',
  },
  grep_search: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
    label: 'Search', color: 'text-purple-400',
  },
  codebase_search: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>,
    label: 'Codebase', color: 'text-purple-400',
  },
  file_search: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>,
    label: 'Find', color: 'text-purple-400',
  },
  list_dir: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2H5a2 2 0 00-2-2z" /></svg>,
    label: 'List', color: 'text-blue-400',
  },
  create_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>,
    label: 'Create', color: 'text-green-400',
  },
  delete_file: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>,
    label: 'Delete', color: 'text-red-400',
  },
  web_search: {
    icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" /></svg>,
    label: 'Web', color: 'text-indigo-400',
  },
};

const DEFAULT_META = {
  icon: <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>,
  label: 'Tool', color: 'text-muted',
};

function getToolMeta(name: string) {
  return TOOL_META[name] || DEFAULT_META;
}

function getToolDescription(call: ToolCall): string {
  const args = call.arguments || {};
  switch (call.name) {
    case 'read_file':
    case 'write_file':
    case 'edit_file':
    case 'replace_in_file':
    case 'create_file':
    case 'delete_file':
      return String(args.path || args.file_path || args.file || '');
    case 'run_command':
    case 'execute_command':
    case 'shell':
      return String(args.command || args.cmd || '').slice(0, 80);
    case 'grep_search':
    case 'codebase_search':
      return String(args.pattern || args.query || args.search || '').slice(0, 60);
    case 'file_search':
      return String(args.pattern || args.query || '').slice(0, 60);
    case 'list_dir':
      return String(args.path || args.dir || '.');
    case 'web_search':
      return String(args.query || '').slice(0, 60);
    default:
      return '';
  }
}

// ── Activity Item ────────────────────────────────────────────────────────
interface ActivityItemProps {
  call: ToolCall;
  isRunning: boolean;
  result?: string;
}

const EnhancedActivityItem = memo(function EnhancedActivityItem({
  call,
  isRunning,
  result,
}: ActivityItemProps) {
  const [expanded, setExpanded] = useState(false);
  const meta = getToolMeta(call.name);
  const desc = getToolDescription(call);
  const hasResult = result !== undefined;

  return (
    <motion.div variants={staggerItem} className="group">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left py-1 px-2 rounded-lg hover:bg-accent/5 transition-colors"
      >
        {/* Status indicator */}
        <span className="shrink-0">
          {isRunning ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
              className="h-3.5 w-3.5 rounded-full border-2 border-primary-500/30 border-t-primary-500"
            />
          ) : hasResult ? (
            <motion.svg
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="h-3.5 w-3.5 text-emerald-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
            </motion.svg>
          ) : (
            <span className={meta.color}>{meta.icon}</span>
          )}
        </span>

        {/* Tool label */}
        <span className={`text-[11px] font-medium shrink-0 ${meta.color}`}>
          {meta.label}
        </span>

        {/* Description */}
        {desc && (
          <span className="text-[11px] text-muted truncate ml-1 flex-1">
            {desc}
          </span>
        )}

        {/* Expand indicator */}
        {hasResult && (
          <motion.svg
            animate={{ rotate: expanded ? 180 : 0 }}
            className="h-3 w-3 text-muted/40 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </motion.svg>
        )}
      </button>

      {/* Expanded content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="ml-5 mt-1 mb-2 p-2.5 rounded-lg bg-background/50 border border-border/50 max-h-48 overflow-auto">
              <pre className="text-[10px] text-muted whitespace-pre-wrap break-all">
                {hasResult ? result : JSON.stringify(call.arguments, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

// ── Activity Entry type ──────────────────────────────────────────────────
export interface ActivityEntry {
  call: ToolCall;
  isRunning: boolean;
  result?: string;
}

export function extractActivities(messages: Message[]): ActivityEntry[] {
  const activities: ActivityEntry[] = [];
  const resultMap = new Map<string, string>();

  for (const msg of messages) {
    if (msg.eventType === 'tool_result' && msg.toolCalls?.[0]) {
      const key = msg.toolCalls[0].id || msg.toolCalls[0].name;
      resultMap.set(key, msg.content);
    }
  }

  for (const msg of messages) {
    if ((msg.eventType === 'tool_call' || msg.eventType === 'tool_dispatch') && msg.toolCalls?.[0]) {
      const call = msg.toolCalls[0];
      const key = call.id || call.name;
      const isRunning = msg.eventType === 'tool_dispatch' || call.arguments?.partial === true;
      activities.push({ call, isRunning, result: resultMap.get(key) });
    }
  }
  return activities;
}

// ── Enhanced AgentActivity Panel ─────────────────────────────────────────
export const EnhancedAgentActivity = memo(function EnhancedAgentActivity({
  activities,
}: {
  activities: ActivityEntry[];
}) {
  if (activities.length === 0) return null;

  const runningCount = activities.filter((a) => a.isRunning).length;
  const completedCount = activities.filter((a) => a.result !== undefined).length;
  const totalCount = activities.length;
  const progressPercent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  return (
    <motion.div
      variants={fadeInUp}
      initial="hidden"
      animate="visible"
      className="my-3 rounded-xl border border-border/60 bg-surface/40 overflow-hidden shadow-lg"
    >
      {/* Header with progress bar */}
      <div className="px-4 py-2.5 border-b border-border/40 bg-surface/60">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {runningCount > 0 ? (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
                className="h-4 w-4 rounded-full border-2 border-primary-500/30 border-t-primary-500"
              />
            ) : (
              <svg className="h-4 w-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            )}
            <span className="text-xs font-semibold text-foreground">Agent Activity</span>
          </div>
          <div className="flex items-center gap-2">
            {runningCount > 0 ? (
              <motion.span
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 1.5, repeat: Infinity }}
                className="flex items-center gap-1 text-[10px] text-primary-400"
              >
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary-400" />
                {runningCount} running
              </motion.span>
            ) : (
              <span className="text-[10px] text-emerald-400">
                ✓ {completedCount} completed
              </span>
            )}
            <span className="text-[10px] text-muted/60">{progressPercent}%</span>
          </div>
        </div>

        {/* Progress bar */}
        <div className="w-full h-1.5 bg-background rounded-full overflow-hidden">
          <motion.div
            className={`h-full ${
              runningCount > 0
                ? 'bg-gradient-to-r from-primary-500 to-purple-500'
                : 'bg-emerald-500'
            }`}
            initial={{ width: 0 }}
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Activity list */}
      <motion.div
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="px-3 py-2 max-h-72 overflow-y-auto space-y-0.5"
      >
        {activities.map((activity, i) => (
          <EnhancedActivityItem
            key={activity.call.id || activity.call.name || i}
            call={activity.call}
            isRunning={activity.isRunning}
            result={activity.result}
          />
        ))}
      </motion.div>
    </motion.div>
  );
});

export default EnhancedAgentActivity;
