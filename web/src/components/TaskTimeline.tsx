'use client';

import type { PlanStep, SessionSummary, Task } from '@/lib/store';

interface TaskTimelineProps {
  tasks: Task[];
  planSteps?: PlanStep[];
  sessions?: SessionSummary[];
}

export function TaskTimeline({ tasks, planSteps = [], sessions = [] }: TaskTimelineProps) {
  return (
    <div className="space-y-6">
      <section className="bg-surface border border-border rounded-lg p-4">
        <h2 className="text-sm font-semibold mb-3">Sessions</h2>
        {sessions.length === 0 && <p className="text-sm text-muted">No sessions yet.</p>}
        <ul className="space-y-2">
          {sessions.map((session) => (
            <li key={session.id} className="text-sm truncate" title={session.id}>
              {session.id}
            </li>
          ))}
        </ul>
      </section>

      <section className="bg-surface border border-border rounded-lg p-4">
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
      </section>

      {planSteps.length > 0 && (
        <section className="bg-surface border border-border rounded-lg p-4">
          <h2 className="text-sm font-semibold mb-3">Plan</h2>
          <ul className="space-y-2">
            {planSteps.map((step) => (
              <li key={step.id} className="text-sm">
                <span className="text-muted mr-2">{step.status}</span>
                {step.description}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
