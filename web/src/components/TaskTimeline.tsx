'use client';

import { useAppStore } from '@/lib/store';

export function TaskTimeline() {
  const tasks = useAppStore((s) => s.tasks);

  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <h2 className="text-sm font-semibold mb-3">Tasks</h2>
      {tasks.length === 0 && <p className="text-sm text-muted">No tasks yet.</p>}
      <ul className="space-y-2">
        {tasks.map((task) => (
          <li key={task.id} className="text-sm">
            <span
              className={`inline-block w-2 h-2 rounded-full mr-2 ${
                task.status === 'running'
                  ? 'bg-yellow-500'
                  : task.status === 'completed'
                  ? 'bg-green-500'
                  : 'bg-red-500'
              }`}
            />
            {task.prompt}
          </li>
        ))}
      </ul>
    </div>
  );
}
