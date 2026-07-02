/**
 * ExtensionLoader — Discovers and loads IDE extensions.
 *
 * Extensions are stored in `.likecodex/extensions/` as directories
 * containing a manifest.json file and optionally a JS entry point.
 *
 * Lifecycle: install → enable → activate → (use) → deactivate → disable → uninstall
 */

import type {
  ExtensionManifest,
  ExtensionActivationResult,
  ExtensionInfo,
  ExtensionStatus,
  ExtensionContribution,
} from './types';
import { CommandRegistry } from './commandRegistry';

const API_BASE = '/api';

/** Minimum fields required in a valid manifest */
const REQUIRED_MANIFEST_FIELDS: (keyof ExtensionManifest)[] = [
  'id', 'name', 'version', 'description', 'author', 'main',
];

class ExtensionLoaderImpl {
  private extensions = new Map<string, ExtensionInfo>();
  private loaded = false;

  // ── Public API ────────────────────────────────────────────

  /** Fetch extension manifests from the backend */
  async loadExtensions(): Promise<void> {
    if (this.loaded) return;
    this.loaded = true;

    try {
      const resp = await fetch('/api/ide/extensions/list');
      if (!resp.ok) return;

      const manifests: ExtensionManifest[] = await resp.json();
      for (const manifest of manifests) {
        const extInfo: ExtensionInfo = {
          manifest,
          status: manifest.enabled ? 'enabled' : 'disabled',
          installedAt: Date.now(),
        };
        this.extensions.set(manifest.id, extInfo);

        if (manifest.enabled) {
          await this.activateExtension(manifest.id);
        }
      }
    } catch (err) {
      console.error('[ExtensionLoader] Failed to load extensions:', err);
    }
  }

  /** Load a single extension from manifest */
  async loadExtension(manifest: ExtensionManifest): Promise<void> {
    const existing = this.extensions.get(manifest.id);
    const extInfo: ExtensionInfo = {
      manifest,
      status: existing?.status || (manifest.enabled ? 'enabled' : 'disabled'),
      installedAt: existing?.installedAt || Date.now(),
      updatedAt: Date.now(),
    };
    this.extensions.set(manifest.id, extInfo);

    if (manifest.enabled) {
      // Register commands from manifest
      if (manifest.contributed?.commands) {
        for (const cmd of manifest.contributed.commands) {
          CommandRegistry.register(cmd.id, (...args) => {
            const info = this.extensions.get(manifest.id);
            const handler = info?.activationResult?.activate?.()?.[cmd.id];
            if (handler) return handler(...args);
            console.warn(`[ExtensionLoader] No handler for command "${cmd.id}" in extension "${manifest.id}"`);
          }, cmd);
        }
      }

      this.extensions.set(manifest.id, extInfo);

      // Try to dynamically import the extension's JS entry point
      if (manifest.main) {
        try {
          const module = await this.sandboxedImport(manifest);
          if (typeof module.activate === 'function') {
            const activation = { activate: module.activate, deactivate: module.deactivate };
            extInfo.activationResult = activation;
            extInfo.status = 'active';

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
          console.debug(`[ExtensionLoader] Extension "${manifest.id}" has no loadable JS entry:`, importErr);
        }
      }

      console.log(`[ExtensionLoader] Loaded: ${manifest.name} v${manifest.version}`);
    }
  }

  /** Validate a manifest before installation */
  validateManifest(manifest: Record<string, unknown>): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    for (const field of REQUIRED_MANIFEST_FIELDS) {
      if (!manifest[field] || String(manifest[field]).trim() === '') {
        errors.push(`Missing required field: ${field}`);
      }
    }
    if (manifest.id && !/^[a-z0-9][a-z0-9._-]*$/.test(String(manifest.id))) {
      errors.push('Invalid id: must start with lowercase alphanumeric, contain only [a-z0-9._-]');
    }
    if (manifest.version && !/^\d+\.\d+\.\d+$/.test(String(manifest.version))) {
      errors.push('Invalid version: must be semver (e.g. 1.0.0)');
    }
    return { valid: errors.length === 0, errors };
  }

  /** Install an extension from a manifest */
  async installExtension(manifest: ExtensionManifest): Promise<boolean> {
    const validation = this.validateManifest(manifest as unknown as Record<string, unknown>);
    if (!validation.valid) {
      console.error('[ExtensionLoader] Invalid manifest:', validation.errors);
      return false;
    }

    if (this.extensions.has(manifest.id)) {
      console.warn(`[ExtensionLoader] Extension "${manifest.id}" already installed`);
      return false;
    }

    try {
      // Save manifest to backend
      const resp = await fetch(`${API_BASE}/ide/extensions/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ manifest }),
      });
      if (!resp.ok) {
        console.error(`[ExtensionLoader] Failed to install extension: ${resp.statusText}`);
        return false;
      }

      const extInfo: ExtensionInfo = {
        manifest,
        status: 'installed',
        installedAt: Date.now(),
      };
      this.extensions.set(manifest.id, extInfo);

      // Run onInstall hook
      if (manifest.scripts?.install) {
        await this.runLifecycleScript(manifest, manifest.scripts.install);
      }

      console.log(`[ExtensionLoader] Installed: ${manifest.name} v${manifest.version}`);
      return true;
    } catch (err) {
      console.error('[ExtensionLoader] Install failed:', err);
      return false;
    }
  }

  /** Enable an extension */
  async enableExtension(id: string): Promise<boolean> {
    const ext = this.extensions.get(id);
    if (!ext) {
      console.warn(`[ExtensionLoader] Extension "${id}" not found`);
      return false;
    }

    try {
      ext.status = 'activating';
      const resp = await fetch('/api/ide/extensions/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, enabled: true }),
      });
      if (!resp.ok) return false;

      // Run onEnable hook
      if (ext.manifest.scripts?.install) {
        // re-use install script as enable hook for simplicity
      }

      await this.activateExtension(id);
      ext.status = 'active';
      ext.manifest.enabled = true;
      return true;
    } catch (err) {
      ext.status = 'error';
      ext.error = String(err);
      return false;
    }
  }

  /** Disable an extension */
  async disableExtension(id: string): Promise<boolean> {
    const ext = this.extensions.get(id);
    if (!ext) return false;

    try {
      ext.status = 'deactivating';
      await this.deactivateExtension(id);

      const resp = await fetch('/api/ide/extensions/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, enabled: false }),
      });
      if (!resp.ok) return false;

      ext.status = 'disabled';
      ext.manifest.enabled = false;
      return true;
    } catch (err) {
      ext.status = 'error';
      ext.error = String(err);
      return false;
    }
  }

  /** Uninstall an extension */
  async uninstallExtension(id: string, permanent: boolean = true): Promise<boolean> {
    const ext = this.extensions.get(id);
    if (!ext) return false;

    try {
      if (ext.manifest.enabled) {
        await this.disableExtension(id);
      }

      if (permanent) {
        const resp = await fetch(`${API_BASE}/ide/extensions/uninstall`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id }),
        });
        if (!resp.ok) throw new Error(resp.statusText);
      }

      // Run onUninstall hook
      if (ext.manifest.scripts?.uninstall) {
        await this.runLifecycleScript(ext.manifest, ext.manifest.scripts.uninstall);
      }

      this.extensions.delete(id);
      console.log(`[ExtensionLoader] Uninstalled: ${ext.manifest.name}`);
      return true;
    } catch (err) {
      console.error('[ExtensionLoader] Uninstall failed:', err);
      ext.status = 'error';
      ext.error = String(err);
      return false;
    }
  }

  /** Unload an extension (runtime only, doesn't touch disk) */
  async unloadExtension(id: string): Promise<void> {
    await this.deactivateExtension(id);
    const ext = this.extensions.get(id);
    if (ext) {
      ext.status = 'disabled';
    }
    this.extensions.delete(id);
  }

  // ── Query ──────────────────────────────────────────────────

  /** Get all loaded extensions */
  getExtensions(): ExtensionInfo[] {
    return Array.from(this.extensions.values());
  }

  /** Get a single extension */
  getExtension(id: string): ExtensionInfo | undefined {
    return this.extensions.get(id);
  }

  /** Check if an extension is loaded */
  isLoaded(id: string): boolean {
    return this.extensions.has(id);
  }

  /** Get extensions by status */
  getExtensionsByStatus(status: ExtensionStatus): ExtensionInfo[] {
    return this.getExtensions().filter((e) => e.status === status);
  }

  /** Get extensions that contribute to a specific area */
  getExtensionsByContribution(type: keyof ExtensionContribution): ExtensionInfo[] {
    return this.getExtensions().filter(
      (e) => e.manifest.contributed?.[type] && e.manifest.contributed[type]!.length > 0
    );
  }

  // ── Private Helpers ────────────────────────────────────────

  private async activateExtension(id: string): Promise<void> {
    const ext = this.extensions.get(id);
    if (!ext || !ext.manifest.main) return;

    try {
      const module = await this.sandboxedImport(ext.manifest);
      if (typeof module.activate === 'function') {
        const activation: ExtensionActivationResult = {
          activate: module.activate,
          deactivate: module.deactivate,
        };
        ext.activationResult = activation;
        ext.status = 'active';

        const handlers = activation.activate?.();
        if (handlers) {
          for (const [cmdId, handler] of Object.entries(handlers)) {
            CommandRegistry.register(cmdId, handler as (...args: unknown[]) => unknown, {
              extensionId: ext.manifest.id,
            });
          }
        }
      }
    } catch (err) {
      console.warn(`[ExtensionLoader] Could not activate "${id}":`, err);
    }
  }

  private async deactivateExtension(id: string): Promise<void> {
    const ext = this.extensions.get(id);
    if (!ext) return;

    ext.activationResult?.deactivate?.();
    ext.activationResult = undefined;

    // Unregister commands
    if (ext.manifest.contributed?.commands) {
      for (const cmd of ext.manifest.contributed.commands) {
        CommandRegistry.unregister(cmd.id);
      }
    }
  }

  /** Sandboxed dynamic import with error isolation */
  private async sandboxedImport(manifest: ExtensionManifest): Promise<Record<string, unknown>> {
    try {
      const module = await import(/* @vite-ignore */ `/extensions/${manifest.id}/${manifest.main}`);
      return module;
    } catch (err) {
      // Isolate error — don't let one extension's failure affect others
      console.debug(`[ExtensionLoader] Sandboxed import failed for "${manifest.id}":`, err);
      return {};
    }
  }

  /** Run a lifecycle script by path */
  private async runLifecycleScript(manifest: ExtensionManifest, scriptPath: string): Promise<void> {
    try {
      const module = await import(/* @vite-ignore */ `/extensions/${manifest.id}/${scriptPath}`);
      if (typeof module.default === 'function') {
        await module.default();
      }
    } catch (err) {
      console.warn(`[ExtensionLoader] Lifecycle script failed for "${manifest.id}":`, err);
    }
  }
}

export const ExtensionLoader = new ExtensionLoaderImpl();
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
