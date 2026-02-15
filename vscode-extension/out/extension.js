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
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const client_1 = require("./client");
const provider_1 = require("./provider");
let client;
let provider;
let providerDisposable;
async function activate(context) {
    console.log('Vishwa Autocomplete extension is now active');
    const outputChannel = vscode.window.createOutputChannel('Vishwa Autocomplete');
    context.subscriptions.push(outputChannel);
    // Initialize client
    client = new client_1.VishwaClient(outputChannel);
    await client.start();
    // Initialize provider
    provider = new provider_1.VishwaCompletionProvider(client, outputChannel);
    // Register inline completion provider
    const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
    if (config.get('enabled', true)) {
        registerProvider(context);
    }
    // Register text document change listener for RL feedback
    context.subscriptions.push(vscode.workspace.onDidChangeTextDocument((event) => {
        if (provider) {
            provider.handleTextDocumentChange(event);
        }
    }));
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('vishwa.autocomplete.toggle', () => {
        const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
        const enabled = config.get('enabled', true);
        config.update('enabled', !enabled, vscode.ConfigurationTarget.Global);
        if (!enabled) {
            registerProvider(context);
            vscode.window.showInformationMessage('Vishwa Autocomplete enabled');
        }
        else {
            unregisterProvider();
            vscode.window.showInformationMessage('Vishwa Autocomplete disabled');
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('vishwa.autocomplete.clearCache', async () => {
        if (client) {
            try {
                await client.clearCache();
                vscode.window.showInformationMessage('Vishwa Autocomplete cache cleared');
            }
            catch (error) {
                vscode.window.showErrorMessage(`Failed to clear cache: ${error}`);
            }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('vishwa.autocomplete.showStats', async () => {
        if (client) {
            try {
                const stats = await client.getStats();
                const message = `
Cache Size: ${stats.cache_size}
Cache Hit Rate: ${(stats.cache_hit_rate * 100).toFixed(1)}%
Total Requests: ${stats.total_requests}
Model: ${stats.model}
                    `.trim();
                vscode.window.showInformationMessage(message);
            }
            catch (error) {
                vscode.window.showErrorMessage(`Failed to get stats: ${error}`);
            }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('vishwa.autocomplete.showRLStats', async () => {
        if (client) {
            try {
                const stats = await client.getRLStats();
                const totalInteractions = stats.total_interactions || 0;
                const bucketCount = Object.keys(stats.buckets || {}).length;
                let message = `RL Stats: ${totalInteractions} interactions, ${bucketCount} buckets\n\n`;
                for (const [bucket, strategies] of Object.entries(stats.buckets || {})) {
                    message += `${bucket}:\n`;
                    for (const [strategy, data] of Object.entries(strategies)) {
                        const d = data;
                        message += `  ${strategy}: mean=${d.mean} obs=${d.observations}${d.disabled ? ' [DISABLED]' : ''}\n`;
                    }
                }
                outputChannel.appendLine(message);
                outputChannel.show();
                vscode.window.showInformationMessage(`RL Stats: ${totalInteractions} interactions across ${bucketCount} buckets. See output channel for details.`);
            }
            catch (error) {
                vscode.window.showErrorMessage(`Failed to get RL stats: ${error}`);
            }
        }
    }));
    // Watch for configuration changes
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration(async (e) => {
        if (e.affectsConfiguration('vishwa.autocomplete.enabled')) {
            const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
            const enabled = config.get('enabled', true);
            if (enabled) {
                registerProvider(context);
            }
            else {
                unregisterProvider();
            }
        }
        if (e.affectsConfiguration('vishwa.autocomplete.model')) {
            const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
            const model = config.get('model', 'gemma3:4b');
            if (client) {
                await client.restart(model);
                outputChannel.appendLine(`Restarted with model: ${model}`);
            }
        }
    }));
    outputChannel.appendLine('Vishwa Autocomplete extension activated successfully (v3 - background fetch)');
}
function registerProvider(context) {
    if (providerDisposable) {
        return; // Already registered
    }
    if (provider) {
        providerDisposable = vscode.languages.registerInlineCompletionItemProvider({ pattern: '**' }, provider);
        context.subscriptions.push(providerDisposable);
    }
}
function unregisterProvider() {
    if (providerDisposable) {
        providerDisposable.dispose();
        providerDisposable = undefined;
    }
}
async function deactivate() {
    if (client) {
        await client.stop();
    }
    unregisterProvider();
}
//# sourceMappingURL=extension.js.map