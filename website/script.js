// ===== Word Rotate Effect =====
class WordRotate {
    constructor(element, words, options = {}) {
        this.element = element;
        this.words = words;
        this.duration = options.duration || 2500;
        this.wordIndex = 0;
        this.start();
    }

    start() {
        setInterval(() => {
            this.wordIndex = (this.wordIndex + 1) % this.words.length;

            // Add exit animation
            this.element.classList.add('fade-out');

            setTimeout(() => {
                this.element.textContent = this.words[this.wordIndex];
                this.element.classList.remove('fade-out');
                this.element.classList.add('fade-in');

                setTimeout(() => {
                    this.element.classList.remove('fade-in');
                }, 400);
            }, 400);
        }, this.duration);
    }
}

// ===== Tab Switching =====
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;

            // Remove active class from all buttons and contents
            tabButtons.forEach(b => b.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // Add active class to clicked button and corresponding content
            btn.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// ===== Copy to Clipboard =====
function initCopyButtons() {
    const copyButtons = document.querySelectorAll('.copy-btn');

    copyButtons.forEach(btn => {
        btn.addEventListener('click', async () => {
            const textToCopy = btn.dataset.copy;

            try {
                await navigator.clipboard.writeText(textToCopy);

                // Visual feedback
                btn.classList.add('copied');
                const originalHTML = btn.innerHTML;
                btn.innerHTML = `
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="20 6 9 17 4 12"/>
                    </svg>
                `;

                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.innerHTML = originalHTML;
                }, 2000);
            } catch (err) {
                console.error('Failed to copy:', err);
            }
        });
    });
}

// ===== Smooth Scroll for Anchor Links =====
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                const headerOffset = 80;
                const elementPosition = target.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });
}

// ===== Intersection Observer for Animations =====
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe feature cards
    document.querySelectorAll('.feature-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        observer.observe(card);
    });

    // Observe workflow steps
    document.querySelectorAll('.workflow-step').forEach((step, index) => {
        step.style.opacity = '0';
        step.style.transform = 'translateY(20px)';
        step.style.transitionDelay = `${index * 100}ms`;
        observer.observe(step);
    });

    // Add CSS for animation
    const style = document.createElement('style');
    style.textContent = `
        .animate-in {
            opacity: 1 !important;
            transform: translateY(0) !important;
            transition: opacity 0.6s ease, transform 0.6s ease;
        }
    `;
    document.head.appendChild(style);
}

// ===== Navbar Background on Scroll =====
function initNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    let lastScroll = 0;

    window.addEventListener('scroll', () => {
        const currentScroll = window.pageYOffset;

        if (currentScroll > 50) {
            navbar.style.background = 'rgba(10, 10, 11, 0.95)';
        } else {
            navbar.style.background = 'rgba(10, 10, 11, 0.8)';
        }

        lastScroll = currentScroll;
    });
}

// ===== Terminal Animation =====
function initTerminalAnimation() {
    const terminalOutput = document.querySelector('.terminal-output');
    if (!terminalOutput) return;

    const lines = terminalOutput.innerHTML.split('<br>');
    terminalOutput.innerHTML = '';

    lines.forEach((line, index) => {
        setTimeout(() => {
            terminalOutput.innerHTML += line + (index < lines.length - 1 ? '<br>' : '');
        }, index * 800);
    });
}

// ===== Initialize Everything =====
document.addEventListener('DOMContentLoaded', () => {
    // Initialize word rotate
    const wordRotateElement = document.getElementById('word-rotate');
    if (wordRotateElement) {
        new WordRotate(wordRotateElement, [
            'AI',
            'code'
        ], {
            duration: 2500
        });
    }

    // Initialize other features
    initTabs();
    initCopyButtons();
    initSmoothScroll();
    initScrollAnimations();
    initNavbarScroll();

    // Delay terminal animation for better effect
    setTimeout(initTerminalAnimation, 1000);
});

// ===== Detect OS for Install Instructions =====
function detectOS() {
    const userAgent = navigator.userAgent.toLowerCase();

    if (userAgent.includes('win')) return 'windows';
    if (userAgent.includes('mac')) return 'mac';
    if (userAgent.includes('linux')) return 'mac'; // Linux uses same commands as mac

    return 'mac';
}

// Auto-select tab based on OS
document.addEventListener('DOMContentLoaded', () => {
    const os = detectOS();
    const tabBtn = document.querySelector(`.tab-btn[data-tab="${os}"]`);

    if (tabBtn) {
        tabBtn.click();
    }
});
