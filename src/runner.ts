import * as vscode from "vscode";
import { PATCHED_PYTHON } from "./common";

let currentTerminal: vscode.Terminal | undefined = undefined;

export async function runFile(file: string) {
  if (!currentTerminal) {
    currentTerminal = vscode.window.createTerminal("Node Python Runner");
  }
  currentTerminal.show(false);
  currentTerminal.sendText(`node ${PATCHED_PYTHON} ${file}`, true);
}
