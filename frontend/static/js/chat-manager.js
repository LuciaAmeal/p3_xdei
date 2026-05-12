/**
 * Chat Manager for XDEI AI Assistant
 * Handles UI interactions and communication with the backend chat endpoint.
 */

class ChatManager {
    constructor() {
        this.messages = [
            {
                role: 'system',
                content: 'Eres un asistente experto en movilidad urbana para la ciudad de A Coruña. Ayudas a los usuarios con información sobre autobuses, rutas, paradas y tiempos de espera. Eres amable, conciso y usas datos en tiempo real cuando están disponibles.'
            }
        ];
        
        this.initElements();
        this.initEventListeners();
        
        // Add the initial greeting to the UI only
        this.addMessage('assistant', 'Hola. Soy tu asistente de movilidad urbana para A Coruña. Puedo ayudarte con información sobre rutas, paradas, ocupación de vehículos o cualquier duda que tengas sobre la plataforma.');
    }

    initElements() {
        this.panel = document.getElementById('chat-panel');
        this.messagesContainer = document.getElementById('chat-messages');
        this.form = document.getElementById('chat-form');
        this.input = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('chat-send');
        this.statusText = document.getElementById('chat-status-text');
    }

    initEventListeners() {
        if (this.form) {
            this.form.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSendMessage();
            });
        }

        // Listen for tab changes to auto-focus input
        document.querySelectorAll('[data-tab-target]').forEach(tab => {
            tab.addEventListener('click', () => {
                if (tab.dataset.tabTarget === 'chat') {
                    setTimeout(() => this.input.focus(), 100);
                }
            });
        });
    }

    async handleSendMessage() {
        const text = this.input.value.trim();
        if (!text || this.sendBtn.disabled) return;

        // Add user message to UI and history
        this.addMessage('user', text);
        this.messages.push({ role: 'user', content: text });
        
        // Clear input and show loading
        this.input.value = '';
        this.setLoading(true);

        try {
            const response = await this.fetchChatCompletion(this.messages);
            const aiText = response.choices[0].message.content;
            
            // Add AI message to UI and history
            this.addMessage('assistant', aiText);
            this.messages.push({ role: 'assistant', content: aiText });
        } catch (error) {
            console.error('Chat error:', error);
            this.addMessage('assistant', 'Lo siento, ha ocurrido un error al conectar con el servicio de IA. Por favor, inténtalo de nuevo más tarde.', true);
        } finally {
            this.setLoading(false);
        }
    }

    async fetchChatCompletion(messages) {
        const url = `${window.BACKEND_BASE_URL}/api/chat`;
        
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('xdei_token') || ''}`
            },
            body: JSON.stringify({ messages })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || error.error || 'Failed to fetch completion');
        }

        return await response.json();
    }

    addMessage(role, content, isError = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message chat-message--${role === 'user' ? 'user' : 'ai'}`;
        if (isError) messageDiv.classList.add('chat-message--error');

        const avatar = role === 'user' ? '👤' : '🤖';
        
        messageDiv.innerHTML = `
            <div class="chat-message__avatar">${avatar}</div>
            <div class="chat-message__content">${this.escapeHtml(content)}</div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    setLoading(isLoading) {
        this.sendBtn.disabled = isLoading;
        this.input.disabled = isLoading;
        
        if (isLoading) {
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'chat-loading';
            loadingDiv.className = 'chat-message chat-message--ai';
            loadingDiv.innerHTML = `
                <div class="chat-message__avatar">🤖</div>
                <div class="chat-message__content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            `;
            this.messagesContainer.appendChild(loadingDiv);
            this.scrollToBottom();
        } else {
            const loadingDiv = document.getElementById('chat-loading');
            if (loadingDiv) loadingDiv.remove();
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTo({
            top: this.messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatManager = new ChatManager();
});
