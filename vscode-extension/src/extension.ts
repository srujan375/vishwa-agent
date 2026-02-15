import * as vscode from 'vscode';
import { VishwaClient } from './client';
import { VishwaCompletionProvider } from './provider';

let client: VishwaClient | undefined;
let provider: VishwaCompletionProvider | undefined;
let providerDisposable: vscode.Disposable | undefined;

export async function activate(context: vscode.ExtensionContext) {
    console.log('Vishwa Autocomplete extension is now active');

    const outputChannel = vscode.window.createOutputChannel('Vishwa Autocomplete');
    context.subscriptions.push(outputChannel);

    // Initialize client
    client = new VishwaClient(outputChannel);
    await client.start();

    // Initialize provider
    provider = new VishwaCompletionProvider(client, outputChannel);

    // Register inline completion provider
    const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
    if (config.get<boolean>('enabled', true)) {
        registerProvider(context);
    }

    // Register text document change listener for RL feedback
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument((event) => {
            if (provider) {
                provider.handleTextDocumentChange(event);
            }
        })
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('vishwa.autocomplete.toggle', () => {
            const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
            const enabled = config.get<boolean>('enabled', true);
            config.update('enabled', !enabled, vscode.ConfigurationTarget.Global);

            if (!enabled) {
                registerProvider(context);
                vscode.window.showInformationMessage('Vishwa Autocomplete enabled');
            } else {
                unregisterProvider();
                vscode.window.showInformationMessage('Vishwa Autocomplete disabled');
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('vishwa.autocomplete.clearCache', async () => {
            if (client) {
                try {
                    await client.clearCache();
                    vscode.window.showInformationMessage('Vishwa Autocomplete cache cleared');
                } catch (error) {
                    vscode.window.showErrorMessage(`Failed to clear cache: ${error}`);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('vishwa.autocomplete.showStats', async () => {
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
                } catch (error) {
                    vscode.window.showErrorMessage(`Failed to get stats: ${error}`);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('vishwa.autocomplete.showRLStats', async () => {
            if (client) {
                try {
                    const stats = await client.getRLStats();
                    const totalInteractions = stats.total_interactions || 0;
                    const bucketCount = Object.keys(stats.buckets || {}).length;

                    let message = `RL Stats: ${totalInteractions} interactions, ${bucketCount} buckets\n\n`;

                    for (const [bucket, strategies] of Object.entries(stats.buckets || {})) {
                        message += `${bucket}:\n`;
                        for (const [strategy, data] of Object.entries(strategies as Record<string, any>)) {
                            const d = data as any;
                            message += `  ${strategy}: mean=${d.mean} obs=${d.observations}${d.disabled ? ' [DISABLED]' : ''}\n`;
                        }
                    }

                    outputChannel.appendLine(message);
                    outputChannel.show();
                    vscode.window.showInformationMessage(`RL Stats: ${totalInteractions} interactions across ${bucketCount} buckets. See output channel for details.`);
                } catch (error) {
                    vscode.window.showErrorMessage(`Failed to get RL stats: ${error}`);
                }
            }
        })
    );

    // Watch for configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration(async (e) => {
            if (e.affectsConfiguration('vishwa.autocomplete.enabled')) {
                const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
                const enabled = config.get<boolean>('enabled', true);

                if (enabled) {
                    registerProvider(context);
                } else {
                    unregisterProvider();
                }
            }

            if (e.affectsConfiguration('vishwa.autocomplete.model')) {
                const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
                const model = config.get<string>('model', 'gemma3:4b');

                if (client) {
                    await client.restart(model);
                    outputChannel.appendLine(`Restarted with model: ${model}`);
                }
            }
        })
    );

    outputChannel.appendLine('Vishwa Autocomplete extension activated successfully (v3 - background fetch)');
}

function registerProvider(context: vscode.ExtensionContext) {
    if (providerDisposable) {
        return; // Already registered
    }

    if (provider) {
        providerDisposable = vscode.languages.registerInlineCompletionItemProvider(
            { pattern: '**' },
            provider
        );
        context.subscriptions.push(providerDisposable);
    }
}

function unregisterProvider() {
    if (providerDisposable) {
        providerDisposable.dispose();
        providerDisposable = undefined;
    }
}

export async function deactivate() {
    if (client) {
        await client.stop();
    }
    unregisterProvider();
}
