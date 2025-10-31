document.addEventListener('alpine:init', () => {
    Alpine.data('copyButton', (textToCopy) => ({
        copied: false,
        textToCopy,

        async copy() {
            try {
                if (navigator.clipboard) {
                    await navigator.clipboard.writeText(this.textToCopy);
                } else {
                    // Fallback для старых браузеров
                    const textarea = document.createElement('textarea');
                    textarea.value = this.textToCopy;
                    document.body.appendChild(textarea);
                    textarea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textarea);
                }
                this.copied = true;
                setTimeout(() => (this.copied = false), 1500);
            } catch (error) {
                console.error('Failed to copy:', error);
            }
        }
    }))
});
