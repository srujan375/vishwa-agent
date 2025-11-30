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
exports.VishwaCompletionProvider = void 0;
const vscode = __importStar(require("vscode"));
class VishwaCompletionProvider {
    constructor(client, outputChannel) {
        this.lastTriggerTime = 0;
        this.client = client;
        this.outputChannel = outputChannel;
    }
    async provideInlineCompletionItems(document, position, context, token) {
        try {
            // Check if autocomplete is enabled
            const config = vscode.workspace.getConfiguration('vishwa.autocomplete');
            const enabled = config.get('enabled', true);
            if (!enabled) {
                return undefined;
            }
            // Check if auto-trigger is enabled
            const autoTrigger = config.get('autoTrigger', true);
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
            // Debounce - default 500ms to avoid rate limiting with cloud APIs
            const debounceDelay = config.get('debounceDelay', 500);
            return new Promise((resolve) => {
                if (this.debounceTimer) {
                    clearTimeout(this.debounceTimer);
                }
                this.debounceTimer = setTimeout(async () => {
                    try {
                        const suggestion = await this.getSuggestion(document, position, token);
                        resolve(suggestion);
                    }
                    catch (error) {
                        this.outputChannel.appendLine(`Error getting suggestion: ${error}`);
                        resolve(undefined);
                    }
                }, debounceDelay);
            });
        }
        catch (error) {
            this.outputChannel.appendLine(`Error in provideInlineCompletionItems: ${error}`);
            return undefined;
        }
    }
    async getSuggestion(document, position, token) {
        try {
            // Check cancellation before making request
            if (token.isCancellationRequested) {
                this.outputChannel.appendLine(`Request cancelled before API call`);
                return undefined;
            }
            const content = document.getText();
            const filePath = document.uri.fsPath;
            const result = await this.client.getSuggestion(filePath, content, position.line, position.character);
            // Check cancellation after API call
            if (token.isCancellationRequested) {
                this.outputChannel.appendLine(`Request cancelled after API call`);
                return undefined;
            }
            if (!result || !result.suggestion) {
                return undefined;
            }
            // Get current line info
            const currentLine = document.lineAt(position.line);
            const textBeforeCursor = currentLine.text.substring(0, position.character);
            const textAfterCursor = currentLine.text.substring(position.character);
            // Clean up the suggestion text
            let suggestionText = result.suggestion;
            // Log raw suggestion for debugging
            this.outputChannel.appendLine(`Raw suggestion: ${JSON.stringify(suggestionText)}`);
            // Strip leading whitespace/newlines that would cause misalignment
            // The suggestion should start right at the cursor position
            suggestionText = suggestionText.replace(/^[\r\n]+/, '');
            // Also strip leading spaces if we're not at the start of a line
            // This prevents double-indentation issues
            if (textBeforeCursor.length > 0) {
                suggestionText = suggestionText.replace(/^[ \t]+/, '');
            }
            this.outputChannel.appendLine(`After cleanup: ${JSON.stringify(suggestionText)}`);
            // Skip empty suggestions
            if (!suggestionText || suggestionText.trim().length === 0) {
                this.outputChannel.appendLine(`Skipping empty suggestion`);
                return undefined;
            }
            // Create inline completion item - no range means insert at cursor
            const item = new vscode.InlineCompletionItem(suggestionText);
            // Log final suggestion
            const cached = result.cached ? '[CACHED]' : '[NEW]';
            this.outputChannel.appendLine(`${cached} Returning suggestion at ${position.line}:${position.character}`);
            this.outputChannel.appendLine(`  Text: ${JSON.stringify(suggestionText.substring(0, 80))}`);
            return [item];
        }
        catch (error) {
            this.outputChannel.appendLine(`Error getting suggestion: ${error}`);
            return undefined;
        }
    }
    isInStringOrComment(document, position) {
        const line = document.lineAt(position.line).text;
        const beforeCursor = line.substring(0, position.character);
        // Detect language
        const languageId = document.languageId;
        // Check for comments
        if (languageId === 'python') {
            if (beforeCursor.includes('#')) {
                return true;
            }
        }
        else if (['javascript', 'typescript', 'java', 'c', 'cpp', 'go', 'rust'].includes(languageId)) {
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
exports.VishwaCompletionProvider = VishwaCompletionProvider;
//# sourceMappingURL=provider.js.map