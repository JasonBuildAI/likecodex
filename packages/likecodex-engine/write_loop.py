import re

with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\loop.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the simple watchdog section with enhanced version
old = "        # Start watchdog\n        self._last_activity_time = time.time()\n\n        iteration = 0\n        hit_max_iterations = False\n        while True:"
new = """        # Start watchdog with 15s check interval and 5min timeout
        self._last_activity_time = time.time()
        self._start_time = time.time()
        self._watchdog_fired = False
        self._watchdog_check_interval = 15
        self._watchdog_timeout = 300

        iteration = 0
        hit_max_iterations = False
        while True:"""
content = content.replace(old, new)

# Enhance the existing watchdog check section
old_watchdog = """            # Watchdog: check if stuck (no tool calls for 5 minutes)
            now = time.time()
            if self._used_any_tool and (now - self._last_activity_time) > 300:
                yield self._emit(
                    LLMResponse(
                        content="[watchdog] No tool calls for 5 minutes. Injecting prompt to check if stuck.",
                        model="system",
                        event_type="notice",
                    )
                )
                self._last_activity_time = now
            self._last_activity_time = now"""
new_watchdog = """            # Watchdog: periodic check (15s interval) with 5min timeout
            now = time.time()
            elapsed = now - self._start_time
            idle_time = now - self._last_activity_time

            # 5-minute absolute timeout
            if elapsed > self._watchdog_timeout and self._used_any_tool:
                yield self._emit(
                    LLMResponse(
                        content="[watchdog] Total execution time exceeded 5 minute timeout. Forcing termination.",
                        model="system",
                        event_type="watchdog_timeout",
                        metadata={
                            "elapsed_s": round(elapsed, 1),
                            "idle_s": round(idle_time, 1),
                            "action": "timeout_termination",
                        },
                    )
                )
                hit_max_iterations = True
                break

            # Idle detection
            if idle_time > self._watchdog_check_interval and self._used_any_tool:
                if not self._watchdog_fired:
                    self._watchdog_fired = True
                    yield self._emit(
                        LLMResponse(
                            content=f"[watchdog] Idle for {idle_time:.0f}s. Checking if stuck.",
                            model="system",
                            event_type="watchdog_check",
                            metadata={
                                "elapsed_s": round(elapsed, 1),
                                "idle_s": round(idle_time, 1),
                                "action": "idle_check",
                            },
                        )
                    )
                # If idle > 60s, inject nudge
                if idle_time > 60:
                    yield self._emit(
                        LLMResponse(
                            content="[watchdog] Extended idle detected. Attempting to re-engage the model.",
                            model="system",
                            event_type="watchdog_idle",
                            metadata={
                                "elapsed_s": round(elapsed, 1),
                                "idle_s": round(idle_time, 1),
                                "action": "idle_nudge",
                            },
                        )
                    )
                    self._last_activity_time = now
                    self._watchdog_fired = False
            else:
                self._watchdog_fired = False
            self._last_activity_time = now"""
content = content.replace(old_watchdog, new_watchdog)

with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\loop.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')
