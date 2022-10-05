import * as path from 'path';
// TODO: This isn't going to work in the browser
export const PATCHED_PYTHON = path.join(__dirname, '..', 'resources', 'patch_cpython', 'output', 'build', 'patched', 'python.js');
export const DEBUGGER_LAUNCHER = path.join(__dirname, '..', 'resources', 'debug', 'debug_file.py' );