'use client';

import type { DoctorReport } from '@/lib/api';

interface SetupBannerProps {
  doctor: DoctorReport | null;
}

export function SetupBanner({ doctor }: SetupBannerProps) {
  if (!doctor || doctor.ok) {
    return null;
  }

  return (
    <div className="border-b border-yellow-600/40 bg-yellow-950/30 px-6 py-3 text-sm">
      <p className="font-medium text-yellow-200">Setup required</p>
      <ul className="mt-1 list-disc pl-5 text-yellow-100/90 space-y-1">
        {!doctor.api_key_configured && (
          <li>Configure your DeepSeek API key: run <code className="rounded bg-black/30 px-1">likecodex setup</code></li>
        )}
        {!doctor.engine_reachable && (
          <li>Start the stack: run <code className="rounded bg-black/30 px-1">likecodex start --web</code></li>
        )}
        {doctor.fix && <li>{doctor.fix}</li>}
      </ul>
    </div>
  );
}
