import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { TextEncoder } from 'util';

/**
 * Check if a Python executable has vishwa installed
 */
function hasVishwaInstalled(pythonPath: string): boolean {
    try {
        const result = cp.spawnSync(pythonPath, ['-c', 'import vishwa.autocomplete.service'], {
            encoding: 'utf8',
            timeout: 5000,
            shell: process.platform === 'win32',
            windowsHide: true
        });
        return result.status === 0;
    } catch {
        return false;
    }
}

/**
 * Check if a Python command/path exists and is executable
 */
function pythonExists(pythonPath: string): boolean {
    try {
        const result = cp.spawnSync(pythonPath, ['--version'], {
            encoding: 'utf8',
            timeout: 5000,
            shell: process.platform === 'win32',
            windowsHide: true
        });
        return result.status === 0;
    } catch {
        return false;
    }
}

/**
 * Get the vishwa project root directory (parent of vscode-extension)
 */
function getVishwaProjectRoot(): string | undefined {
    try {
        // __dirname in compiled JS will be in 'out' folder
        // vscode-extension/out/client.js -> vscode-extension -> vishwa (project root)
        const extensionDir = path.resolve(__dirname, '..');
        const projectRoot = path.resolve(extensionDir, '..');

        // Verify this looks like the vishwa project
        if (fs.existsSync(path.join(projectRoot, 'src', 'vishwa')) ||
            fs.existsSync(path.join(projectRoot, 'pyproject.toml'))) {
            return projectRoot;
        }
    } catch {
        // Ignore errors
    }
    return undefined;
}

/**
 * Get platform-specific Python candidates
 * Returns paths where Python is commonly installed on each OS
 */
function getPlatformPythonCandidates(): string[] {
    const homeDir = os.homedir();
    const candidates: string[] = [];

    // FIRST PRIORITY: Check vishwa project's own venv (where pip install -e . was run)
    const vishwaRoot = getVishwaProjectRoot();
    if (vishwaRoot) {
        if (process.platform === 'win32') {
            // Common venv names on Windows
            candidates.push(path.join(vishwaRoot, 'vishwa', 'Scripts', 'python.exe'));
            candidates.push(path.join(vishwaRoot, 'venv', 'Scripts', 'python.exe'));
            candidates.push(path.join(vishwaRoot, '.venv', 'Scripts', 'python.exe'));
        } else {
            // Common venv names on macOS/Linux
            candidates.push(path.join(vishwaRoot, 'vishwa', 'bin', 'python'));
            candidates.push(path.join(vishwaRoot, 'venv', 'bin', 'python'));
            candidates.push(path.join(vishwaRoot, '.venv', 'bin', 'python'));
        }
    }

    // SECOND PRIORITY: User's home directory vishwa installation (~/.vishwa/)
    if (process.platform === 'win32') {
        candidates.push(path.join(homeDir, '.vishwa', 'Scripts', 'python.exe'));
        candidates.push(path.join(homeDir, '.vishwa', 'venv', 'Scripts', 'python.exe'));
    } else {
        candidates.push(path.join(homeDir, '.vishwa', 'bin', 'python'));
        candidates.push(path.join(homeDir, '.vishwa', 'venv', 'bin', 'python'));
    }

    switch (process.platform) {
        case 'win32':
            // Windows: Check Python launcher, common install locations, user installs
            candidates.push(
                // Python launcher (recommended way on Windows)
                'py',
                'python',
                'python3',
                // User-local installs (Microsoft Store, python.org installer)
                path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python313', 'python.exe'),
                path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python312', 'python.exe'),
                path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
                path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
                // System-wide installs
                'C:\\Python313\\python.exe',
                'C:\\Python312\\python.exe',
                'C:\\Python311\\python.exe',
                'C:\\Python310\\python.exe',
                // Anaconda/Miniconda
                path.join(homeDir, 'anaconda3', 'python.exe'),
                path.join(homeDir, 'miniconda3', 'python.exe'),
                path.join(process.env.PROGRAMDATA || '', 'anaconda3', 'python.exe'),
                path.join(process.env.PROGRAMDATA || '', 'miniconda3', 'python.exe'),
            );
            break;

        case 'darwin':
            // macOS: Homebrew (Apple Silicon & Intel), pyenv, system Python
            candidates.push(
                // Command-line (will use PATH)
                'python3',
                'python',
                // Homebrew on Apple Silicon
                '/opt/homebrew/bin/python3',
                '/opt/homebrew/bin/python3.13',
                '/opt/homebrew/bin/python3.12',
                '/opt/homebrew/bin/python3.11',
                // Homebrew on Intel Mac
                '/usr/local/bin/python3',
                '/usr/local/bin/python3.13',
                '/usr/local/bin/python3.12',
                '/usr/local/bin/python3.11',
                // pyenv
                path.join(homeDir, '.pyenv', 'shims', 'python'),
                path.join(homeDir, '.pyenv', 'shims', 'python3'),
                // macOS system Python (available since macOS 12.3+)
                '/usr/bin/python3',
                // Anaconda/Miniconda
                path.join(homeDir, 'anaconda3', 'bin', 'python'),
                path.join(homeDir, 'miniconda3', 'bin', 'python'),
                '/opt/anaconda3/bin/python',
                '/opt/miniconda3/bin/python',
            );
            break;

        case 'linux':
        default:
            // Linux: System Python, pyenv, user installs
            candidates.push(
                // Command-line (will use PATH)
                'python3',
                'python',
                // System Python locations
                '/usr/bin/python3',
                '/usr/bin/python',
                '/usr/local/bin/python3',
                '/usr/local/bin/python',
                // pyenv
                path.join(homeDir, '.pyenv', 'shims', 'python'),
                path.join(homeDir, '.pyenv', 'shims', 'python3'),
                // User local bin (pip install --user)
                path.join(homeDir, '.local', 'bin', 'python3'),
                path.join(homeDir, '.local', 'bin', 'python'),
                // Anaconda/Miniconda
                path.join(homeDir, 'anaconda3', 'bin', 'python'),
                path.join(homeDir, 'miniconda3', 'bin', 'python'),
                '/opt/anaconda3/bin/python',
                '/opt/miniconda3/bin/python',
            );
            break;
    }

    return candidates;
}

/**
 * Auto-detect Python executable path that has vishwa installed.
 *
 * Priority order:
 * 1. User-configured path (always respected)
 * 2. System/global Python with vishwa installed
 * 3. VS Code workspace Python with vishwa installed
 * 4. Any available Python (will show clear error about missing vishwa)
 *
 * Works on Windows, macOS, and Linux.
 */
async function detectPythonPath(): Promise<string> {
    const candidates: string[] = [];
    const checkedPaths = new Set<string>();

    // Helper to add unique candidates
    const addCandidate = (pythonPath: string) => {
        if (pythonPath && !checkedPaths.has(pythonPath)) {
            checkedPaths.add(pythonPath);
            if (pythonExists(pythonPath)) {
                candidates.push(pythonPath);
            }
        }
    };

    // 1. Check if user has explicitly configured a path (highest priority)
    const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
    const configuredPath = config.get<string>('pythonPath', '');
    if (configuredPath && configuredPath !== 'python' && configuredPath !== 'auto') {
        if (fs.existsSync(configuredPath) || pythonExists(configuredPath)) {
            // User explicitly configured - use it directly
            return configuredPath;
        }
    }

    // 2. Add platform-specific Python candidates (system/global installs)
    const platformCandidates = getPlatformPythonCandidates();
    for (const pythonPath of platformCandidates) {
        addCandidate(pythonPath);
    }

    // 3. Try to get Python path from VS Code Python extension (workspace interpreter)
    const pythonExtension = vscode.extensions.getExtension('ms-python.python');
    if (pythonExtension) {
        if (!pythonExtension.isActive) {
            try {
                await pythonExtension.activate();
            } catch {
                // Ignore activation errors
            }
        }
        try {
            const pythonApi = pythonExtension.exports;
            let workspacePython: string | undefined;

            if (pythonApi?.settings?.getExecutionDetails) {
                const details = pythonApi.settings.getExecutionDetails(
                    vscode.workspace.workspaceFolders?.[0]?.uri
                );
                if (details?.execCommand?.[0]) {
                    workspacePython = details.execCommand[0];
                }
            }
            // Alternative API for newer versions
            if (!workspacePython && pythonApi?.environments?.getActiveEnvironmentPath) {
                const envPath = await pythonApi.environments.getActiveEnvironmentPath();
                if (envPath?.path) {
                    workspacePython = envPath.path;
                }
            }

            if (workspacePython) {
                addCandidate(workspacePython);
            }
        } catch {
            // Ignore errors from Python extension API
        }
    }

    // 4. Find the first Python that has vishwa installed
    for (const pythonPath of candidates) {
        if (hasVishwaInstalled(pythonPath)) {
            return pythonPath;
        }
    }

    // 5. No Python with vishwa found - return first available Python
    // The service will fail with a clear error about missing vishwa module
    if (candidates.length > 0) {
        return candidates[0];
    }

    // 6. Last resort fallback
    return process.platform === 'win32' ? 'python' : 'python3';
}

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
        this.outputChannel.appendLine(`Detecting Python with vishwa installed...`);

        // Log the vishwa project root for debugging
        const vishwaRoot = getVishwaProjectRoot();
        if (vishwaRoot) {
            this.outputChannel.appendLine(`Vishwa project root: ${vishwaRoot}`);
        } else {
            this.outputChannel.appendLine(`Vishwa project root: not found`);
        }

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

            // Set timeout (15s for warm Ollama models - first request may be slower)
            setTimeout(() => {
                if (this.pendingRequests.has(id)) {
                    this.pendingRequests.delete(id);
                    reject(new Error('Request timeout'));
                }
            }, 15000);
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
