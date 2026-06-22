'use client';

import { useEffect, useState } from 'react';
import { fetchSkills } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';

export function SkillPanel() {
  const skills = useAppStore((s) => s.skills);
  const setSkills = useAppStore((s) => s.setSkills);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (skills.length > 0) return;
    setLoading(true);
    fetchSkills().then((data) => {
      setSkills(data);
    }).catch(() => {}).finally(() => setLoading(false));
  }, [skills.length, setSkills]);

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold mb-3">Skills</h2>
      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted py-2">
          <div className="h-3 w-3 animate-spin rounded-full border border-primary border-t-transparent" />
          Loading skills...
        </div>
      ) : skills.length === 0 ? (
        <p className="text-xs text-muted">No skills available.</p>
      ) : (
        <ul className="space-y-2 max-h-64 overflow-y-auto">
          {skills.map((skill) => (
            <li key={skill.name} className="rounded border border-border p-2">
              <div className="text-sm font-medium">{skill.name}</div>
              <div className="text-xs text-muted mt-0.5">{skill.description}</div>
              {skill.source && (
                <div className="text-[10px] text-muted mt-1">{skill.source}</div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
