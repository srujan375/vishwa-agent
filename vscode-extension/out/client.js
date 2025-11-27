"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.VishwaClient = void 0;
const vscode = __importStar(require("vscode"));
const cp = __importStar(require("child_process"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/**
 * Auto-detect Python executable path
 * Tries multiple strategies in order of preference
 */
async function detectPythonPath() {
    // 1. Check if user has explicitly configured a path
    const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
    const configuredPath = config.get('pythonPath', '');
    if (configuredPath && configuredPath !== 'python' && configuredPath !== 'auto') {
        // User has set a custom path, validate it exists
        if (fs.existsSync(configuredPath)) {
            return configuredPath;
        }
    }
    // 2. Try to get Python path from VS Code Python extension
    const pythonExtension = vscode.extensions.getExtension('ms-python.python');
    if (pythonExtension) {
        if (!pythonExtension.isActive) {
            try {
                await pythonExtension.activate();
            }
            catch {
                // Ignore activation errors
            }
        }
        try {
            const pythonApi = pythonExtension.exports;
            if (pythonApi?.settings?.getExecutionDetails) {
                const details = pythonApi.settings.getExecutionDetails(vscode.workspace.workspaceFolders?.[0]?.uri);
                if (details?.execCommand?.[0]) {
                    return details.execCommand[0];
                }
            }
            // Alternative API for newer versions
            if (pythonApi?.environments?.getActiveEnvironmentPath) {
                const envPath = await pythonApi.environments.getActiveEnvironmentPath();
                if (envPath?.path) {
                    return envPath.path;
                }
            }
        }
        catch {
            // Ignore errors from Python extension API
        }
    }
    // 3. Try common Python commands
    const pythonCommands = process.platform === 'win32'
        ? ['python', 'python3', 'py']
        : ['python3', 'python'];
    for (const cmd of pythonCommands) {
        try {
            const result = cp.spawnSync(cmd, ['--version'], {
                encoding: 'utf8',
                timeout: 5000,
                shell: process.platform === 'win32'
            });
            if (result.status === 0) {
                return cmd;
            }
        }
        catch {
            // Command not found, try next
        }
    }
    // 4. Check common installation paths
    const commonPaths = process.platform === 'win32'
        ? [
            path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
            path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
            path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python39', 'python.exe'),
            path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
            'C:\\Python311\\python.exe',
            'C:\\Python310\\python.exe',
            'C:\\Python39\\python.exe',
            'C:\\Python312\\python.exe',
        ]
        : [
            '/usr/bin/python3',
            '/usr/local/bin/python3',
            '/opt/homebrew/bin/python3',
            '/usr/bin/python',
        ];
    for (const pythonPath of commonPaths) {
        if (fs.existsSync(pythonPath)) {
            return pythonPath;
        }
    }
    // 5. Fallback to 'python' and hope for the best
    return 'python';
}
class VishwaClient {
    constructor(outputChannel) {
        this.requestId = 0;
        this.pendingRequests = new Map();
        this.buffer = '';
        this.outputChannel = outputChannel;
    }
    async start() {
        const pythonPath = await detectPythonPath();
        this.outputChannel.appendLine(`Starting Vishwa service (model from .env)`);
        this.outputChannel.appendLine(`Using Python: ${pythonPath}`);
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
        }
        catch (error) {
            this.outputChannel.appendLine(`Failed to start service: ${error}`);
            throw error;
        }
    }
    async stop() {
        if (this.process) {
            this.process.kill();
            this.process = undefined;
        }
    }
    async restart(model) {
        await this.stop();
        await this.start();
    }
    handleStdout(data) {
        this.buffer += data.toString();
        let newlineIndex;
        while ((newlineIndex = this.buffer.indexOf('\n')) !== -1) {
            const line = this.buffer.substring(0, newlineIndex);
            this.buffer = this.buffer.substring(newlineIndex + 1);
            if (line.trim()) {
                try {
                    const response = JSON.parse(line);
                    this.handleResponse(response);
                }
                catch (error) {
                    this.outputChannel.appendLine(`Failed to parse response: ${line}`);
                }
            }
        }
    }
    handleResponse(response) {
        const pending = this.pendingRequests.get(response.id);
        if (!pending) {
            this.outputChannel.appendLine(`Received response for unknown request ID: ${response.id}`);
            return;
        }
        this.pendingRequests.delete(response.id);
        if (response.error) {
            pending.reject(new Error(response.error.message));
        }
        else {
            pending.resolve(response.result);
        }
    }
    async sendRequest(method, params) {
        if (!this.process || !this.process.stdin) {
            throw new Error('Vishwa service not running');
        }
        const id = ++this.requestId;
        const request = {
            jsonrpc: '2.0',
            method,
            params,
            id
        };
        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, { resolve, reject });
            const requestJson = JSON.stringify(request) + '\n';
            this.process.stdin.write(requestJson);
            // Set timeout
            setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 10000); // 10 second timeout
        });
    }
    async ping() {
        await this.sendRequest('ping', {});
    }
    async getSuggestion(filePath, content, line, character, contextLines) {
        const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
        const defaultContextLines = config.get('contextLines', 20);
        const result = await this.sendRequest('getSuggestion', {
            file_path: filePath,
            content,
            cursor: { line, character },
            context_lines: contextLines ?? defaultContextLines
        });
        return result;
    }
    async clearCache() {
        await this.sendRequest('clearCache', {});
    }
    async getStats() {
        const result = await this.sendRequest('getStats', {});
        return result;
    }
}
exports.VishwaClient = VishwaClient;
//# sourceMappingURL=client.js.map