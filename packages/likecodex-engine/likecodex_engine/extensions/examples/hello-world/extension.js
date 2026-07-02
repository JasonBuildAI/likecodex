/**
 * Hello World Extension
 *
 * Demonstrates the LikeCodex plugin system with three commands:
 * 1. hello-world.sayHello - Display a friendly message
 * 2. hello-world.showTime - Show current date/time
 * 3. hello-world.greet - Greet a user by name
 *
 * This extension registers command handlers that are called
 * when the user invokes them from the command palette.
 */

/**
 * Called when the extension is activated (enabled).
 * Returns a map of command ID → handler function.
 */
export function activate() {
  console.log('[HelloWorld] Extension activated!');

  return {
    'hello-world.sayHello': (...args) => {
      const name = args[0] || 'World';
      console.log(`[HelloWorld] Hello, ${name}!`);
      return `Hello, ${name}! 👋`;
    },

    'hello-world.showTime': () => {
      const now = new Date();
      const formatted = now.toLocaleString();
      console.log(`[HelloWorld] Current time: ${formatted}`);
      return `Current time: ${formatted}`;
    },

    'hello-world.greet': (...args) => {
      const name = args[0] || 'friend';
      const greeting = args[1] || 'Hello';
      const message = `${greeting}, ${name}! Welcome to LikeCodex extensions.`;
      console.log(`[HelloWorld] ${message}`);
      return message;
    },
  };
}

/**
 * Called when the extension is deactivated (disabled).
 * Clean up resources here (event listeners, intervals, etc.).
 */
export function deactivate() {
  console.log('[HelloWorld] Extension deactivated.');
}
