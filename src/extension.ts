// The module 'vscode' contains the VS Code extensibility API
// Import the module and reference it with the alias vscode in your code below
import * as vscode from 'vscode';
import { DebugAdapterDescriptorFactory, DebugConfigurationProvider, debugFile } from './debugger';
import { runFile } from './runner';

// this method is called when your extension is activated
// your extension is activated the very first time the command is executed
export function activate(context: vscode.ExtensionContext) {
	
 	// The command has been defined in the package.json file
	// Now provide the implementation of the command with registerCommand
	// The commandId parameter must match the command field in package.json
	let disposable = vscode.commands.registerCommand('debugpyweb.runwithnode', () => {
		// The code you place here will be executed every time your command is executed
		// Display a message box to the user
		if (vscode.window.activeTextEditor?.document.languageId === 'python') {
			runFile(vscode.window.activeTextEditor?.document.fileName)
		} else {
			vscode.window.showErrorMessage(`Active file has to be a python file`);
		}
	});
	disposable = vscode.commands.registerCommand('debugpyweb.debugwithnode', () => {
		if (vscode.window.activeTextEditor?.document.languageId === 'python') {
			debugFile(vscode.window.activeTextEditor?.document.fileName)
		} else {
			vscode.window.showErrorMessage(`Active file has to be a python file`);
		}
	})

	context.subscriptions.push(disposable);

	const provider = new DebugConfigurationProvider();
	context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider('python-node-emscripten', provider));

	const factory = new DebugAdapterDescriptorFactory(context);
	context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory('python-node-emscripten', factory));	
}

// this method is called when your extension is deactivated
export function deactivate() {}
