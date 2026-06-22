/** Debug types for the debugging and testing UI */

export type DebugStatus = 'stopped' | 'running' | 'paused';

export type BreakpointType = 'regular' | 'conditional' | 'logpoint';

export interface Breakpoint {
  id: string;
  filePath: string;
  line: number;
  enabled: boolean;
  condition?: string;
  hitCount?: number;
  logMessage?: string;
}

export interface StackFrame {
  id: number;
  name: string;
  filePath: string;
  line: number;
  column: number;
}

export interface Variable {
  name: string;
  value: string;
  type: string;
  variablesReference: number;
  children?: Variable[];
}

export type TestStatus = 'pending' | 'running' | 'passed' | 'failed' | 'skipped';

export interface TestCase {
  id: string;
  name: string;
  filePath: string;
  line: number;
  status: TestStatus;
  duration: number;
  errorMessage: string;
  errorStack: string;
}

export interface TestFile {
  path: string;
  framework: string;
  tests: TestCase[];
}
