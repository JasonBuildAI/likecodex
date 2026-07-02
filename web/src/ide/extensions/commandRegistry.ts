/**
 * CommandRegistry — Central registry for commands contributed by extensions.
 * Commands can be invoked by ID and are searchable in the Command Palette.
 */

import type { CommandDefinition } from './types';

type CommandHandler = (...args: unknown[]) => unknown;

interface RegisteredCommand extends CommandDefinition {
  handler: CommandHandler;
  extensionId?: string;
}

type CommandDefPartial = Partial<CommandDefinition> & { extensionId?: string };

class CommandRegistryImpl {
  private commands = new Map<string, RegisteredCommand>();

  register(id: string, handler: CommandHandler, def?: CommandDefPartial): void {
    this.commands.set(id, {
      id,
      label: def?.label || id,
      description: def?.description,
      keybindings: def?.keybindings,
      handler,
    });
  }

  unregister(id: string): void {
    this.commands.delete(id);
  }

  execute(id: string, ...args: unknown[]): unknown {
    const cmd = this.commands.get(id);
    if (cmd) {
      try {
        return cmd.handler(...args);
      } catch (err) {
        console.error(`[CommandRegistry] Error executing "${id}":`, err);
      }
    }
    return undefined;
  }

  get(id: string): RegisteredCommand | undefined {
    return this.commands.get(id);
  }

  getAllCommands(): RegisteredCommand[] {
    return Array.from(this.commands.values());
  }

  search(query: string): RegisteredCommand[] {
    const q = query.toLowerCase();
    return this.getAllCommands().filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(q) ||
        cmd.id.toLowerCase().includes(q) ||
        (cmd.description?.toLowerCase().includes(q) ?? false)
    );
  }
}

export const CommandRegistry = new CommandRegistryImpl();
