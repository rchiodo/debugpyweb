import * as vscode from 'vscode';
import { DebugProtocol } from '@vscode/debugprotocol';
import * as sync from '@vscode/sync-api-common/node';
import * as worker from 'worker_threads';
import { DEBUGGER_LAUNCHER, PATCHED_PYTHON } from './common';
import { SocketRequests } from './requests';
import { WaitableQueue } from './waitableQueue';

class DebugAdapter implements vscode.DebugAdapter {
    private _connection: sync.ServiceConnection<SocketRequests> | undefined;
    private _worker: worker.Worker | undefined;
    private _pythonFile: string | undefined;
    private _readQueue = new WaitableQueue();

    private _didSendMessageEmitter: vscode.EventEmitter<vscode.DebugProtocolMessage> = new vscode.EventEmitter<vscode.DebugProtocolMessage>();

    constructor(private readonly session: vscode.DebugSession, private readonly context: vscode.ExtensionContext) {
        this._pythonFile = session.configuration.program;
    }
    get onDidSendMessage(): vscode.Event<vscode.DebugProtocolMessage> {
        return this._didSendMessageEmitter.event;
    }
    handleMessage(message: DebugProtocol.ProtocolMessage): void {
        if (message.type === 'request') {
            this._handleRequest(message as DebugProtocol.Request);
        }
    }
    dispose() {
        // Should close down the worker
        this._worker?.terminate();
        this._readQueue.clear();
        
    }
    _handleRequest(message: DebugProtocol.Request) {
        switch (message.command) {
            case 'initialize':
                this._handleInitialize(message.arguments);
                break;

            default:
                break;
        }
        this._consumeMessage(message);
    }

    _handleInitialize(args: DebugProtocol.InitializeRequestArguments) {
        if (!this._connection) {
            // Start debugpy in the worker, with it launching the python file
            // See README https://github.com/Microsoft/DEBUGPY
            //this._worker = new worker.Worker(PATCHED_PYTHON,{ argv: [DEBUGGER_LAUNCHER, '--listen', '5678', '--wait-for-client', '--log-to', '~/source/debugpyweb/temp', this._pythonFile] });
            this._worker = new worker.Worker(PATCHED_PYTHON, {argv: ['-c', `print("foo from python ${process.pid}")`]});
            this._worker.on('error', (e) => {
                console.error(e);
            })
            this._worker.on('message', (v) => {
                console.log(`Worker message: ${v}`);
            })
            this._worker.on('messageerror', (e) => {
                console.log(`Worker error: ${e}`);
            })
            this._worker.on('exit', (code) => {
                console.log(`Debugger exited with code ${code}`);
            });

            // Create the connection to the worker
            this._connection = new sync.ServiceConnection<SocketRequests>(this._worker);

            // Setup the handling.
            this._connection.onRequest('socket/read', this._handleRead.bind(this));
            this._connection.onRequest('socket/write', this._handleWrite.bind(this));
            this._connection.onRequest('socket/recvfrom', this._handleReceiveFrom.bind(this));
            this._connection.onRequest('socket/close', this._handleClose.bind(this));

            // Signal ready
            this._connection.signalReady();
        }
    }

    _consumeMessage(message: DebugProtocol.Request) {
        // Stick the message into the queue
        this._readQueue?.enqueue(message);
    }

    async _handleRead(args: {length: number}) {
        // Read the next message out and send it back
        const message = await this._readQueue.dequeue();
        return { errno: 0, data: { value: JSON.stringify(message) } };
    }
    async _handleReceiveFrom(args: {length: number}) {
        // Read the next message out and send it back
        const message = await this._readQueue.dequeue();
        return { errno: 0, data: { value: JSON.stringify(message) } };
    }
    async _handleWrite(args: {message: string}) {
        // Read the message into a protocol 
        const message = JSON.parse(args.message) as DebugProtocol.ProtocolMessage;

        // Send this as an event
        this._didSendMessageEmitter.fire(message);

        return { errno: 0 };
    }
    async _handleClose() {
        // Read the next message out and send it back
        return { errno: 0 };
    }

}

export class DebugAdapterDescriptorFactory implements vscode.DebugAdapterDescriptorFactory {
	constructor(private readonly context: vscode.ExtensionContext) {
	}
	async createDebugAdapterDescriptor(session: vscode.DebugSession): Promise<vscode.DebugAdapterDescriptor> {
		return new vscode.DebugAdapterInlineImplementation(new DebugAdapter(session, this.context));
	}
}

export class DebugConfigurationProvider implements DebugConfigurationProvider {

	/**
	 * Massage a debug configuration just before a debug session is being launched,
	 * e.g. add all missing attributes to the debug configuration.
	 */
	async resolveDebugConfiguration(folder: vscode.WorkspaceFolder | undefined, config: vscode.DebugConfiguration, token?: vscode.CancellationToken): Promise<vscode.DebugConfiguration | undefined> {
		if (!config.type && !config.request && !config.name) {
			const editor = vscode.window.activeTextEditor;
			if (editor && editor.document.languageId === 'python') {
				config.type = 'python-node-emscripten';
				config.name = 'Launch';
				config.request = 'launch';
				config.program = '${file}';
				config.stopOnEntry = false;
			}
		}

		if (!config.program) {
			await vscode.window.showInformationMessage('Cannot find a Python file to debug');
			return undefined;
		}

		return config;
	}
}

export function debugFile(file: string) {
    vscode.debug.startDebugging(undefined, {
        type: 'python-node-emscripten',
        program: file,
        name: 'Debug python in emscripten',
        stopOnEntry: false,
        request: 'launch'
    });
}