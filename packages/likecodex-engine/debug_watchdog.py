with open('d:\\App\\AgentProjects\\likecodex\\likecodex\\packages\\likecodex-engine\\likecodex_engine\\agent\\loop.py', 'rb') as f:
    raw = f.read()
idx = raw.find(b'Watchdog: check')
if idx >= 0:
    print('Found at byte position:', idx)
    # Print 300 bytes around it
    print(repr(raw[idx:idx+260]))
else:
    print('Not found')
    # Try alternate phrasing
    idx = raw.find(b'watchdog')
    if idx >= 0:
        print('Found watchdog at:', idx)
        print(repr(raw[idx:idx+200]))
