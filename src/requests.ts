import { VariableResult } from "@vscode/sync-api-common";

export declare type SocketRequests = {
    /**
     * Read from a socket
     */
    method: 'socket/read';
    params: {
        length: number;
    };
    result: VariableResult<Uint8Array>;
} | {
    /**
     * Wait for bytes from a socket
     */
    method: 'socket/recvfrom';
    params: {
        length: number;
    };
    result: VariableResult<Uint8Array>;
} | {
    /**
     * Write to a socket
     */
    method: 'socket/write';
    params: {
        buffer: Uint8Array
    };
    result: VariableResult<Uint8Array>;
} | {
    /**
     * Close the socket
     */
    method: 'socket/close';
    params: null;
    result: null;
};