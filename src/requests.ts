import { DebugProtocol } from "@vscode/debugprotocol";
import { VariableResult } from "@vscode/sync-api-common";

export declare type SocketRequests = {
    /**
     * Read from a socket
     */
    method: 'socket/read';
    params: {
        length: number;
    };
    result: VariableResult<string>;
} | {
    /**
     * Wait for bytes from a socket
     */
    method: 'socket/recvfrom';
    params: {
        length: number;
    };
    result: VariableResult<string>;
} | {
    /**
     * Write to a socket
     */
    method: 'socket/write';
    params: {
        message: string
    };
    result: VariableResult<string>;
} | {
    /**
     * Close the socket
     */
    method: 'socket/close';
    params: null;
    result: null;
};