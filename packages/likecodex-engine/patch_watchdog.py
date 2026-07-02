with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\loop.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_watchdog = (
    '            # Watchdog: check if stuck (no tool calls for 5 minutes)\n'
    '            now = time.time()\n'
    '            if self._used_any_tool and (now - self._last_activity_time) > 300:\n'
    '                yield self._emit(\n'
    '                    LLMResponse(\n'
    '                        content="[watchdog] No tool calls for 5 minutes. Injecting prompt to check if stuck.",\n'
    '                        model="system",\n'
    '                        event_type="notice",\n'
    '                    )\n'
    '                )\n'
    '                self._last_activity_time = now\n'
    '            self._last_activity_time = now'
)

new_watchdog = (
    '            # Watchdog: periodic check (15s interval) with 5min timeout\n'
    '            now = time.time()\n'
    '            elapsed = now - self._start_time\n'
    '            idle_time = now - self._last_activity_time\n'
    '\n'
    '            # 5-minute absolute timeout\n'
    '            if elapsed > self._watchdog_timeout and self._used_any_tool:\n'
    '                yield self._emit(\n'
    '                    LLMResponse(\n'
    '                        content="[watchdog] Total execution time exceeded 5 minute timeout. Forcing termination.",\n'
    '                        model="system",\n'
    '                        event_type="watchdog_timeout",\n'
    '                        metadata={{\n'
    '                            "elapsed_s": round(elapsed, 1),\n'
    '                            "idle_s": round(idle_time, 1),\n'
    '                            "action": "timeout_termination",\n'
    '                        }},\n'
    '                    )\n'
    '                )\n'
    '                hit_max_iterations = True\n'
    '                break\n'
    '\n'
    '            # Idle detection\n'
    '            if idle_time > self._watchdog_check_interval and self._used_any_tool:\n'
    '                if not self._watchdog_fired:\n'
    '                    self._watchdog_fired = True\n'
    '                    yield self._emit(\n'
    '                        LLMResponse(\n'
    '                            content=f"[watchdog] Idle for {idle_time:.0f}s. Checking if stuck.",\n'
    '                            model="system",\n'
    '                            event_type="watchdog_check",\n'
    '                            metadata={{\n'
    '                                "elapsed_s": round(elapsed, 1),\n'
    '                                "idle_s": round(idle_time, 1),\n'
    '                                "action": "idle_check",\n'
    '                            }},\n'
    '                        )\n'
    '                    )\n'
    '                if idle_time > 60:\n'
    '                    yield self._emit(\n'
    '                        LLMResponse(\n'
    '                            content="[watchdog] Extended idle detected. Attempting to re-engage the model.",\n'
    '                            model="system",\n'
    '                            event_type="watchdog_idle",\n'
    '                            metadata={{\n'
    '                                "elapsed_s": round(elapsed, 1),\n'
    '                                "idle_s": round(idle_time, 1),\n'
    '                                "action": "idle_nudge",\n'
    '                            }},\n'
    '                        )\n'
    '                    )\n'
    '                    self._last_activity_time = now\n'
    '                    self._watchdog_fired = False\n'
    '            else:\n'
    '                self._watchdog_fired = False\n'
    '            self._last_activity_time = now\n'
    '            now_ms = int(time.time() * 1000)\n'
)

if old_watchdog in content:
    content = content.replace(old_watchdog, new_watchdog)
    with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\loop.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Old watchdog pattern not found')
    idx = content.find('Watchdog: check')
    if idx >= 0:
        print('Found at', idx)
        print(repr(content[idx:idx+200]))
