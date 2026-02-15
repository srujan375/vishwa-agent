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
        // Background fetch state
        this.fetchInProgress = false;
        this.client = client;
        this.outputChannel = outputChannel;
    }
    /**
     * Handle document text changes to detect accept/reject of suggestions.
     * Called from extension.ts via onDidChangeTextDocument.
     */
    handleTextDocumentChange(event) {
        if (!this.pendingSuggestion) {
            return;
        }
        const pending = this.pendingSuggestion;
        // Check if the change is in the same file
        if (event.document.uri.fsPath !== pending.filePath) {
            return;
        }
        for (const change of event.contentChanges) {
            const changeLine = change.range.start.line;
            const changeChar = change.range.start.character;
            // Check if change is at the expected position
            if (changeLine !== pending.line) {
                continue;
            }
            // Accept detection: the inserted text matches the suggestion
            if (change.text === pending.suggestionText ||
                (pending.suggestionText.startsWith(change.text) && change.text.length > 0 && change.text.length >= pending.suggestionText.length * 0.8)) {
                this.sendFeedback(true);
                return;
            }
            // Reject detection: user typed something different at the suggestion position
            if (changeChar >= pending.character && change.text.length > 0 && !pending.suggestionText.startsWith(change.text)) {
                this.sendFeedback(false);
                return;
            }
        }
    }
    /**
     * Mark the pending suggestion as implicitly rejected when a new
     * suggestion is requested at a different position.
     */
    rejectPendingIfStale(filePath, line, character) {
        if (!this.pendingSuggestion) {
            return;
        }
        const pending = this.pendingSuggestion;
        // Different file or different line means the old suggestion was skipped
        if (pending.filePath !== filePath || pending.line !== line) {
            this.sendFeedback(false);
        }
    }
    sendFeedback(accepted) {
        if (!this.pendingSuggestion) {
            return;
        }
        const pending = this.pendingSuggestion;
        const latencyMs = Date.now() - pending.timestamp;
        this.pendingSuggestion = undefined;
        this.client.sendFeedback(pending.suggestionId, accepted, latencyMs).catch(err => {
            this.outputChannel.appendLine(`[feedback] Error sending feedback: ${err}`);
        });
        this.outputChannel.appendLine(`[feedback] ${accepted ? 'ACCEPTED' : 'REJECTED'} strategy=${pending.strategy} bucket=${pending.bucket} latency=${latencyMs}ms`);
    }
    async provideInlineCompletionItems(document, position, context, token) {
        const requestId = Date.now().toString(36);
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
            // Skip if in string or comment
            if (this.isInStringOrComment(document, position)) {
                return undefined;
            }
            // Skip if file is too large
            if (document.lineCount > 10000) {
                return undefined;
            }
            const filePath = document.uri.fsPath;
            const currentLine = document.lineAt(position.line).text;
            // Reject stale pending suggestion if cursor moved to different location
            this.rejectPendingIfStale(filePath, position.line, position.character);
            // Try to use cached suggestion
            const cachedResult = this.getCachedSuggestion(filePath, position, currentLine);
            if (cachedResult) {
                this.outputChannel.appendLine(`[${requestId}] Cache hit: "${cachedResult.substring(0, 40)}..."`);
                // Trigger background refresh if cache is getting old (> 2 seconds)
                if (this.cache && Date.now() - this.cache.timestamp > 2000) {
                    this.triggerBackgroundFetch(document, position, config);
                }
                return [new vscode.InlineCompletionItem(cachedResult)];
            }
            // No cache hit - trigger background fetch and return nothing for now
            this.triggerBackgroundFetch(document, position, config);
            this.outputChannel.appendLine(`[${requestId}] No cache, background fetch triggered`);
            return undefined;
        }
        catch (error) {
            this.outputChannel.appendLine(`[${requestId}] Error: ${error}`);
            return undefined;
        }
    }
    getCachedSuggestion(filePath, position, currentLine) {
        if (!this.cache) {
            return undefined;
        }
        // Must be same file
        if (this.cache.filePath !== filePath) {
            return undefined;
        }
        // Must be same line
        if (this.cache.line !== position.line) {
            return undefined;
        }
        // Check if user has typed more on the same line (type-through)
        const cachedLinePrefix = this.cache.lineContent.substring(0, this.cache.character);
        const currentLinePrefix = currentLine.substring(0, position.character);
        // Current position must be at or after cached position
        if (position.character < this.cache.character) {
            return undefined;
        }
        // The line up to cached position must match
        if (!currentLinePrefix.startsWith(cachedLinePrefix)) {
            return undefined;
        }
        // Check what user typed since cache was created
        const typedSinceCached = currentLine.substring(this.cache.character, position.character);
        // The suggestion must start with what the user typed
        if (!this.cache.suggestion.startsWith(typedSinceCached)) {
            return undefined;
        }
        // Return the remaining suggestion
        const remaining = this.cache.suggestion.substring(typedSinceCached.length);
        if (remaining.length === 0) {
            return undefined;
        }
        return remaining;
    }
    triggerBackgroundFetch(document, position, config) {
        // Clear any existing debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        const debounceDelay = config.get('debounceDelay', 300);
        this.debounceTimer = setTimeout(() => {
            this.doBackgroundFetch(document, position);
        }, debounceDelay);
    }
    async doBackgroundFetch(document, position) {
        // Skip if already fetching for similar position
        const filePath = document.uri.fsPath;
        if (this.fetchInProgress && this.lastFetchPosition) {
            const sameFile = this.lastFetchPosition.file === filePath;
            const sameLine = this.lastFetchPosition.line === position.line;
            const nearbyChar = Math.abs(this.lastFetchPosition.character - position.character) < 5;
            if (sameFile && sameLine && nearbyChar) {
                this.outputChannel.appendLine(`[bg] Skipping - similar fetch in progress`);
                return;
            }
        }
        this.fetchInProgress = true;
        this.lastFetchPosition = { line: position.line, character: position.character, file: filePath };
        const requestId = `bg-${Date.now().toString(36)}`;
        this.outputChannel.appendLine(`[${requestId}] Starting background fetch at ${position.line}:${position.character}`);
        try {
            const content = document.getText();
            const currentLine = document.lineAt(position.line).text;
            const result = await this.client.getSuggestion(filePath, content, position.line, position.character);
            if (result && result.suggestion) {
                let suggestionText = result.suggestion;
                // Clean up suggestion
                suggestionText = suggestionText.replace(/^[\r\n]+/, '');
                const textBeforeCursor = currentLine.substring(0, position.character);
                if (textBeforeCursor.length > 0) {
                    suggestionText = suggestionText.replace(/^[ \t]+/, '');
                }
                if (suggestionText && suggestionText.trim().length > 0) {
                    // Store in cache
                    this.cache = {
                        suggestion: suggestionText,
                        line: position.line,
                        character: position.character,
                        lineContent: currentLine,
                        filePath: filePath,
                        timestamp: Date.now()
                    };
                    // Track pending suggestion for RL feedback
                    if (result.suggestion_id) {
                        // Reject any previous pending suggestion
                        if (this.pendingSuggestion) {
                            this.sendFeedback(false);
                        }
                        this.pendingSuggestion = {
                            suggestionId: result.suggestion_id,
                            strategy: result.strategy || '',
                            bucket: result.bucket || '',
                            timestamp: Date.now(),
                            suggestionText: suggestionText,
                            line: position.line,
                            character: position.character,
                            filePath: filePath,
                        };
                    }
                    this.outputChannel.appendLine(`[${requestId}] Cached: "${suggestionText.substring(0, 50)}..." strategy=${result.strategy || 'n/a'}`);
                    // Trigger VS Code to re-request completions
                    vscode.commands.executeCommand('editor.action.inlineSuggest.trigger');
                }
                else {
                    this.outputChannel.appendLine(`[${requestId}] Empty suggestion received`);
                }
            }
            else {
                this.outputChannel.appendLine(`[${requestId}] No suggestion from API`);
            }
        }
        catch (error) {
            this.outputChannel.appendLine(`[${requestId}] Error: ${error}`);
        }
        finally {
            this.fetchInProgress = false;
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