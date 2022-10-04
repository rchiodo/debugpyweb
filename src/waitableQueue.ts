import * as vscode from 'vscode';
import { DebugProtocol } from "@vscode/debugprotocol";

export class WaitableQueue {
    _queue: DebugProtocol.ProtocolMessage[] = [];
    _pushedEmitter: vscode.EventEmitter<DebugProtocol.ProtocolMessage> = new vscode.EventEmitter<DebugProtocol.ProtocolMessage>();

    enqueue(message: DebugProtocol.ProtocolMessage) {
        this._queue.push(message);
        this._pushedEmitter.fire(message);
    }

    async dequeue() : Promise<DebugProtocol.ProtocolMessage> {
        if (this._queue.length > 0) {
            return this._queue.shift()!;
        }
        return new Promise<DebugProtocol.ProtocolMessage>((resolve, _reject) => {
            let disposable: vscode.Disposable;
            disposable = this._pushedEmitter.event((m) => {
                disposable.dispose();
                resolve(this._queue.shift()!);
            })
        });
    }

    clear() {
        this._queue = [];
    }
}