import * as vscode from 'vscode';
import * as cp from 'child_process';
import { TextEncoder } from 'util';

interface JsonRpcRequest {
    jsonrpc: string;
    method: string;
    params: any;
    id: number;
}

interface JsonRpcResponse {
    jsonrpc: string;
    result?: any;
    error?: {
        code: number;
        message: string;
    };
    id: number;
}

interface SuggestionResult {
    suggestion: string;
    type: string;
    cached: boolean;
}

interface StatsResult {
    cache_size: number;
    cache_hit_rate: number;
    total_requests: number;
    model: string;
}

export class VishwaClient {
    private process: cp.ChildProcess | undefined;
    private requestId: number = 0;
    private pendingRequests: Map<number, { resolve: (value: any) => void; reject: (reason: any) => void }> = new Map();
    private buffer: string = '';
    private outputChannel: vscode.OutputChannel;

    constructor(outputChannel: vscode.OutputChannel) {
        this.outputChannel = outputChannel;
    }

    async start(): Promise<void> {
        const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
        const pythonPath = config.get<string>('pythonPath', 'python');

        this.outputChannel.appendLine(`Starting Vishwa service (model from .env)`);

        try {
            // Don't pass --model flag, let service use .env configuration
            this.process = cp.spawn(pythonPath, [
                '-m',
                'vishwa.autocomplete.service'
            ]);

            this.process.stdout?.on('data', (data) => {
                this.handleStdout(data);
            });

            this.process.stderr?.on('data', (data) => {
                const message = data.toString();
                this.outputChannel.appendLine(`[STDERR] ${message}`);
            });

            this.process.on('error', (error) => {
                this.outputChannel.appendLine(`Process error: ${error.message}`);
                vscode.window.showErrorMessage(`Vishwa service error: ${error.message}`);
            });

            this.process.on('exit', (code, signal) => {
                this.outputChannel.appendLine(`Process exited with code ${code}, signal ${signal}`);
                if (code !== 0 && code !== null) {
                    vscode.window.showErrorMessage(`Vishwa service exited unexpectedly (code ${code})`);
                }
            });

            // Send ping to verify connection
            await this.ping();
            this.outputChannel.appendLine('Vishwa service started successfully');
        } catch (error) {
            this.outputChannel.appendLine(`Failed to start service: ${error}`);
            throw error;
        }
    }

    async stop(): Promise<void> {
        if (this.process) {
            this.process.kill();
            this.process = undefined;
        }
    }

    async restart(model?: string): Promise<void> {
        await this.stop();
        await this.start();
    }

    private handleStdout(data: Buffer): void {
        this.buffer += data.toString();

        let newlineIndex;
        while ((newlineIndex = this.buffer.indexOf('\n')) !== -1) {
            const line = this.buffer.substring(0, newlineIndex);
            this.buffer = this.buffer.substring(newlineIndex + 1);

            if (line.trim()) {
                try {
                    const response: JsonRpcResponse = JSON.parse(line);
                    this.handleResponse(response);
                } catch (error) {
                    this.outputChannel.appendLine(`Failed to parse response: ${line}`);
                }
            }
        }
    }

    private handleResponse(response: JsonRpcResponse): void {
        const pending = this.pendingRequests.get(response.id);
        if (!pending) {
            this.outputChannel.appendLine(`Received response for unknown request ID: ${response.id}`);
            return;
        }

        this.pendingRequests.delete(response.id);

        if (response.error) {
            pending.reject(new Error(response.error.message));
        } else {
            pending.resolve(response.result);
        }
    }

    private async sendRequest(method: string, params: any): Promise<any> {
        if (!this.process || !this.process.stdin) {
            throw new Error('Vishwa service not running');
        }

        const id = ++this.requestId;
        const request: JsonRpcRequest = {
            jsonrpc: '2.0',
            method,
            params,
            id
        };

        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, { resolve, reject });

            const requestJson = JSON.stringify(request) + '\n';
            this.process!.stdin!.write(requestJson);

            // Set timeout
            setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 10000); // 10 second timeout
        });
    }

    async ping(): Promise<void> {
        await this.sendRequest('ping', {});
    }

    async getSuggestion(
        filePath: string,
        content: string,
        line: number,
        character: number,
        contextLines?: number
    ): Promise<SuggestionResult> {
        const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
        const defaultContextLines = config.get<number>('contextLines', 20);

        const result = await this.sendRequest('getSuggestion', {
            file_path: filePath,
            content,
            cursor: { line, character },
            context_lines: contextLines ?? defaultContextLines
        });

        return result as SuggestionResult;
    }

    async clearCache(): Promise<void> {
        await this.sendRequest('clearCache', {});
    }

    async getStats(): Promise<StatsResult> {
        const result = await this.sendRequest('getStats', {});
        return result as StatsResult;
    }
}
