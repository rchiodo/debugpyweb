import * as vscode from "vscode";
import * as path from 'path';

let currentTerminal: vscode.Terminal | undefined = undefined;

export async function runFile(file: string) {
  if (!currentTerminal) {
    currentTerminal = vscode.window.createTerminal("Node Python Runner");
  }
  currentTerminal.show(false);
  currentTerminal.sendText(`node ${path.join(__dirname, '..', 'resources', 'patch_cpython', 'output', 'build', 'patched', 'python.js')} ${file}`, true);
}
