'use client';

import { AskRequest } from '@/lib/store';
import { respondAsk } from '@/lib/api';
import { useState } from 'react';

interface AskModalProps {
  requests: AskRequest[];
  onResponded: (requestId: string) => void;
}

export function AskModal({ requests, onResponded }: AskModalProps) {
  const current = requests[0];
  const [selections, setSelections] = useState<Record<number, string[]>>({});

  if (!current) return null;

  const submit = async () => {
    const answers = current.questions.map((q, index) => ({
      questionIndex: index,
      selected: selections[index] || [],
    }));
    await respondAsk(current.requestId, answers);
    onResponded(current.requestId);
    setSelections({});
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-lg p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto">
        <h3 className="text-lg font-semibold mb-4">Agent Question</h3>
        {current.questions.map((q, qi) => (
          <div key={qi} className="mb-4">
            <p className="font-medium text-sm mb-2">{q.question}</p>
            <div className="space-y-2">
              {q.options.map((opt) => (
                <label key={opt.label} className="flex items-start gap-2 text-sm">
                  <input
                    type={q.multiSelect ? 'checkbox' : 'radio'}
                    name={`ask-${qi}`}
                    checked={(selections[qi] || []).includes(opt.label)}
                    onChange={() => {
                      setSelections((prev) => {
                        const cur = prev[qi] || [];
                        if (q.multiSelect) {
                          const next = cur.includes(opt.label)
                            ? cur.filter((x) => x !== opt.label)
                            : [...cur, opt.label];
                          return { ...prev, [qi]: next };
                        }
                        return { ...prev, [qi]: [opt.label] };
                      });
                    }}
                  />
                  <span>
                    {opt.label}
                    {opt.description ? (
                      <span className="block text-muted text-xs">{opt.description}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          </div>
        ))}
        <div className="flex justify-end">
          <button
            type="button"
            onClick={submit}
            className="px-4 py-2 rounded bg-primary text-white text-sm hover:bg-blue-600"
          >
            Submit answers
          </button>
        </div>
      </div>
    </div>
  );
}
