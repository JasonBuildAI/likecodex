path = r'd:\App\AgentProjects\likecodex\likecodex\web\src\app\page.tsx'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ===== 1. Fix embedded CRLF characters that split the file =====
# Step 1a: Join lines (the file has CR/LF inside string literals)
content = content.replace('\r\n', 'LINEBREAK')
content = content.replace('\n', 'LINEBREAK')
content = content.replace('\r', '')

# Step 1b: Fix the known problematic patterns
content = content.replace("beforeCursor[atIndex - 1] === ' 'LINEBREAK')) {", "beforeCursor[atIndex - 1] === '\\\\n')) {")
content = content.replace("query.includes(' 'LINEBREAK') &&", "query.includes('\\\\n') &&")

# Remove remaining LINEBREAK markers
content = content.replace('LINEBREAK', '')

# ===== 2. Add framer-motion import (if not already present) =====
if 'framer-motion' not in content:
    content = content.replace(
        "import { useCallback, useEffect, useRef, useState } from 'react';import { ChatMessages",
        "import { useCallback, useEffect, useRef, useState } from 'react';import { motion, AnimatePresence } from 'framer-motion';import { ChatMessages"
    )

# ===== 3. Add motion.aside wrapper for the chat panel =====
# The chat aside starts with: `{chatOpen && (          <aside`
# And ends with: `</aside>        )}      </div>`
# We need to change it to: `{chatOpen && (          <motion.aside`
# With motion animation props added
# And `</motion.aside>` for the closing tag

# Find the specific chat aside (the second one, which has width w-[480px])
old_aside_open = "{chatOpen && (          <aside            className=\"w-[480px]"
new_aside_open = "{chatOpen && (          <motion.aside            initial={{ opacity: 0, x: 50 }}            animate={{ opacity: 1, x: 0 }}            exit={{ opacity: 0, x: 50 }}            transition={{ type: 'spring', stiffness: 200, damping: 25 }}            className=\"w-[480px]"
content = content.replace(old_aside_open, new_aside_open)

# Close the motion.aside - find the specific one after the chat panel content
# The left panel aside has className="w-56 border-r..."
# The right panel motion.aside doesn't exist yet, so we need to change the existing </aside> that belongs to it
# Strategy: change the LAST </aside> in the file (which is the chat panel aside)
# Actually, let me just replace the specific chat panel closing tag

# The left panel closes with: </aside>        {/* Center:
old_aside_close = "</aside>        )}      </div>"
new_aside_close = "</motion.aside>        )}      </div>"
content = content.replace(old_aside_close, new_aside_close)

# ===== 4. Add motion.button for workspace selector =====
# Find the workspace selector button in the chat panel
old_work_btn = "className=\"w-[480px]"
# The workspace button is the first button after the chat panel header
# Let's just target: <button className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10">                  <span>{currentSessionId ? 'likecodex' : 'New Agent'}
old_btn = "<button className=\"flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10\">                  <span>{currentSessionId ? 'likecodex' : 'New Agent'}</span>"
new_btn = "<motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className=\"flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10\">                  <span>{currentSessionId ? 'likecodex' : 'New Agent'}</span>"
content = content.replace(old_btn, new_btn)

# Also close the motion.button - find the corresponding </button>
# After the workspace button SVG there's </button>, we need to change it to </motion.button>
# But we need to be specific. Let's find the right one.
# The workspace button has a specific pattern:
old_btn_close = "</button>                                {/* Local/Remote indicator */}"
new_btn_close = "</motion.button>                                {/* Local/Remote indicator */}"
content = content.replace(old_btn_close, new_btn_close)

# ===== 5. Add motion.button for settings gear =====
old_settings_btn = "<button                  onClick={() => setIdeSettingsOpen(true)}                  className=\"p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors\"                  title=\"Settings (Ctrl+,)\"                >"
new_settings_btn = "<motion.button                  whileHover={{ scale: 1.05 }}                  whileTap={{ scale: 0.95 }}                  onClick={() => setIdeSettingsOpen(true)}                  className=\"p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors\"                  title=\"Settings (Ctrl+,)\"                >"
content = content.replace(old_settings_btn, new_settings_btn)

old_settings_close = "</button>              </div>            </div>            {/* Chat messages area */}"
new_settings_close = "</motion.button>              </div>            </div>            {/* Chat messages area */}"
content = content.replace(old_settings_close, new_settings_close)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed page.tsx successfully')
