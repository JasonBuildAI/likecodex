/**
 * ExtensionLoader — Discovers and loads IDE extensions.
 *
 * Extensions are stored in `.likecodex/extensions/` as directories
 * containing a manifest.json file and optionally a JS entry point.
 */

import type { ExtensionManifest, ExtensionActivationResult } from './types';
import { CommandRegistry } from './commandRegistry';

class ExtensionLoaderImpl {
  private extensions = new Map<string, ExtensionManifest>();
  private activationResults = new Map<string, ExtensionActivationResult>();
  private loaded = false;

  /** Fetch extension manifests from the backend */
  async loadExtensions(): Promise<void> {
    if (this.loaded) return;
    this.loaded = true;

    try {
      const resp = await fetch('/api/ide/extensions/list');
      if (!resp.ok) return;

      const manifests: ExtensionManifest[] = await resp.json();
      for (const manifest of manifests) {
        if (manifest.enabled) {
          await this.loadExtension(manifest);
        }
      }
    } catch (err) {
      console.error('[ExtensionLoader] Failed to load extensions:', err);
    }
  }

  /** Load a single extension */
  async loadExtension(manifest: ExtensionManifest): Promise<void> {
    try {
      // Register commands from manifest
      if (manifest.contributes?.commands) {
        for (const cmd of manifest.contributes.commands) {
          // Commands are registered with placeholder handlers
          // The actual handler comes from the extension's activate() function
          CommandRegistry.register(cmd.id, (...args) => {
            const result = this.activationResults.get(manifest.id);
            const handler = result?.activate?.()[cmd.id];
            if (handler) return handler(...args);
            console.warn(`[ExtensionLoader] No handler for command "${cmd.id}" in extension "${manifest.id}"`);
          }, cmd);
        }
      }

      this.extensions.set(manifest.id, manifest);

      // Try to dynamically import the extension's JS entry point
      if (manifest.main) {
        try {
          const module = await import(/* @vite-ignore */ `/extensions/${manifest.id}/${manifest.main}`);
          if (typeof module.activate === 'function') {
            const activation = { activate: module.activate, deactivate: module.deactivate };
            this.activationResults.set(manifest.id, activation);

            // Register all commands from the activated extension
            const handlers = activation.activate?.();
            if (handlers) {
              for (const [cmdId, handler] of Object.entries(handlers)) {
                CommandRegistry.register(cmdId, handler as (...args: unknown[]) => unknown, {
                  extensionId: manifest.id,
                });
              }
            }
          }
        } catch (importErr) {
          // Extension JS file might not exist yet — that's OK
          console.debug(`[ExtensionLoader] Extension "${manifest.id}" has no loadable JS entry:`, importErr);
        }
      }

      console.log(`[ExtensionLoader] Loaded: ${manifest.name} v${manifest.version}`);
    } catch (err) {
      console.error(`[ExtensionLoader] Failed to load extension "${manifest.id}":`, err);
    }
  }

  /** Unload an extension */
  async unloadExtension(id: string): Promise<void> {
    const result = this.activationResults.get(id);
    result?.deactivate?.();
    this.activationResults.delete(id);

    const manifest = this.extensions.get(id);
    if (manifest?.contributes?.commands) {
      for (const cmd of manifest.contributes.commands) {
        CommandRegistry.unregister(cmd.id);
      }
    }
    this.extensions.delete(id);
  }

  /** Get all loaded extensions */
  getExtensions(): ExtensionManifest[] {
    return Array.from(this.extensions.values());
  }

  /** Get a single extension */
  getExtension(id: string): ExtensionManifest | undefined {
    return this.extensions.get(id);
  }

  /** Check if an extension is loaded */
  isLoaded(id: string): boolean {
    return this.extensions.has(id);
  }
}

export const ExtensionLoader = new ExtensionLoaderImpl();
