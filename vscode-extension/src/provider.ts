import * as vscode from 'vscode';
import { VishwaClient } from './client';

export class VishwaCompletionProvider implements vscode.InlineCompletionItemProvider {
    private client: VishwaClient;
    private outputChannel: vscode.OutputChannel;
    private lastTriggerTime: number = 0;
    private debounceTimer: NodeJS.Timeout | undefined;

    constructor(client: VishwaClient, outputChannel: vscode.OutputChannel) {
        this.client = client;
        this.outputChannel = outputChannel;
    }

    async provideInlineCompletionItems(
        document: vscode.TextDocument,
        position: vscode.Position,
        context: vscode.InlineCompletionContext,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | vscode.InlineCompletionList | undefined> {
        try {
            // Check if autocomplete is enabled
            const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
            const enabled = config.get<boolean>('enabled', true);
            if (!enabled) {
                return undefined;
            }

            // Check if auto-trigger is enabled
            const autoTrigger = config.get<boolean>('autoTrigger', true);
            if (!autoTrigger && context.triggerKind !== vscode.InlineCompletionTriggerKind.Invoke) {
                return undefined;
            }

            // Detect rapid typing
            const now = Date.now();
            const timeSinceLastTrigger = now - this.lastTriggerTime;
            this.lastTriggerTime = now;

            if (timeSinceLastTrigger < 100) {
                // User is typing rapidly, skip suggestion
                return undefined;
            }

            // Skip if in string or comment
            if (this.isInStringOrComment(document, position)) {
                return undefined;
            }

            // Skip if file is too large
            if (document.lineCount > 10000) {
                return undefined;
            }

            // Debounce
            const debounceDelay = config.get<number>('debounceDelay', 200);

            return new Promise((resolve) => {
                if (this.debounceTimer) {
                    clearTimeout(this.debounceTimer);
                }

                this.debounceTimer = setTimeout(async () => {
                    try {
                        const suggestion = await this.getSuggestion(document, position, token);
                        resolve(suggestion);
                    } catch (error) {
                        this.outputChannel.appendLine(`Error getting suggestion: ${error}`);
                        resolve(undefined);
                    }
                }, debounceDelay);
            });
        } catch (error) {
            this.outputChannel.appendLine(`Error in provideInlineCompletionItems: ${error}`);
            return undefined;
        }
    }

    private async getSuggestion(
        document: vscode.TextDocument,
        position: vscode.Position,
        token: vscode.CancellationToken
    ): Promise<vscode.InlineCompletionItem[] | undefined> {
        try {
            const content = document.getText();
            const filePath = document.uri.fsPath;

            const result = await this.client.getSuggestion(
                filePath,
                content,
                position.line,
                position.character
            );

            if (token.isCancellationRequested) {
                return undefined;
            }

            if (!result || !result.suggestion) {
                return undefined;
            }

            // Create inline completion item
            const item = new vscode.InlineCompletionItem(
                result.suggestion,
                new vscode.Range(position, position)
            );

            // Add metadata for debugging
            if (result.cached) {
                this.outputChannel.appendLine(`[CACHED] Suggestion at ${position.line}:${position.character}`);
            }

            return [item];
        } catch (error) {
            this.outputChannel.appendLine(`Error getting suggestion: ${error}`);
            return undefined;
        }
    }

    private isInStringOrComment(document: vscode.TextDocument, position: vscode.Position): boolean {
        const line = document.lineAt(position.line).text;
        const beforeCursor = line.substring(0, position.character);

        // Detect language
        const languageId = document.languageId;

        // Check for comments
        if (languageId === 'python') {
            if (beforeCursor.includes('#')) {
                return true;
            }
        } else if (['javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust'].includes(languageId)) {
            if (beforeCursor.includes('//')) {
                return true;
            }
            // Simple multi-line comment detection
            const textBeforeCursor = document.getText(new vscode.Range(new vscode.Position(0, 0), position));
            const openComments = (textBeforeCursor.match(/\/\*/g) || []).length;
            const closeComments = (textBeforeCursor.match(/\*\//g) || []).length;
            if (openComments > closeComments) {
                return true;
            }
        }

        // Check for strings (simple detection)
        const singleQuotes = (beforeCursor.match(/'/g) || []).length;
        const doubleQuotes = (beforeCursor.match(/"/g) || []).length;
        const backticks = (beforeCursor.match(/`/g) || []).length;

        // If odd number of quotes, we're likely inside a string
        if (singleQuotes % 2 === 1 || doubleQuotes % 2 === 1 || backticks % 2 === 1) {
            return true;
        }

        return false;
    }
}
