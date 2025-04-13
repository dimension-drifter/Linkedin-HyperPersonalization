// Main JavaScript for the LinkedIn tool
document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    setupTabs();
    
    // Mobile menu toggle
    setupMobileMenu();
    
    // Form submission handlers
    setupFormHandlers();
    
    // Initialize hover and animation effects
    initAnimations();
});

// Handle tab switching
function setupTabs() {
    const tabs = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active classes
            tabs.forEach(t => {
                t.classList.remove('border-primary', 'text-primary');
                t.classList.add('border-transparent', 'text-gray-500');
                
                // Reset the tab indicator
                const indicator = t.querySelector('span:last-child');
                if (indicator) {
                    indicator.classList.remove('scale-x-100');
                    indicator.classList.add('scale-x-0');
                }
            });
            
            // Add active class to clicked tab
            tab.classList.remove('border-transparent', 'text-gray-500');
            tab.classList.add('border-primary', 'text-primary');
            
            // Animate the tab indicator
            const indicator = tab.querySelector('span:last-child');
            if (indicator) {
                indicator.classList.remove('scale-x-0');
                indicator.classList.add('scale-x-100');
            }
            
            // Hide all tab panes
            tabPanes.forEach(pane => {
                pane.classList.add('hidden');
            });
            
            // Show corresponding tab pane
            const tabId = tab.id;
            const paneId = 'content-' + tabId.split('-')[1];
            document.getElementById(paneId).classList.remove('hidden');
        });
    });
    
    // Button shortcuts to tabs
    document.getElementById('btn-batch')?.addEventListener('click', () => {
        document.getElementById('tab-batch').click();
    });
    
    document.getElementById('btn-history')?.addEventListener('click', () => {
        document.getElementById('tab-history').click();
    });
}

// Handle mobile menu toggle
function setupMobileMenu() {
    const menuButton = document.getElementById('mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    
    if (menuButton && mobileMenu) {
        menuButton.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
        });
    }
}

// Handle form submissions
function setupFormHandlers() {
    // Single profile processing
    const processProfileBtn = document.getElementById('process-profile');
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingMessage = document.getElementById('loading-message');
    const profileResults = document.getElementById('profile-results');
    
    if (processProfileBtn) {
        processProfileBtn.addEventListener('click', () => {
            const linkedinUrl = document.getElementById('linkedin-url').value.trim();
            
            if (!linkedinUrl) {
                alert('Please enter a LinkedIn profile URL');
                return;
            }
            
            // Show loading spinner
            loadingSpinner.classList.remove('hidden');
            loadingMessage.textContent = 'Processing LinkedIn profile...';
            
            // Simulate API call (replace with actual API call)
            setTimeout(() => {
                // Hide loading spinner
                loadingSpinner.classList.add('hidden');
                
                // Show results
                profileResults.classList.remove('hidden');
                
                // Populate with mock data (replace with actual API response data)
                document.getElementById('result-name').textContent = 'John Doe';
                document.getElementById('result-headline').textContent = 'Software Engineer at Tech Company';
                document.getElementById('result-location').textContent = 'San Francisco Bay Area';
                document.getElementById('result-company').textContent = 'Tech Company Inc.';
                document.getElementById('result-summary').textContent = 'Experienced software engineer with a focus on web technologies and machine learning.';
                document.getElementById('result-message').textContent = `Hi John, I noticed you're a software engineer at Tech Company. I'm working on a project that involves some of the technologies you specialize in, and I'd love to connect to discuss potential collaboration opportunities. Would you be open to a quick chat this week?`;
                document.getElementById('character-count').textContent = '269';
                
                // Apply text scramble effect to new content
                document.querySelectorAll('.scramble-text').forEach(element => {
                    new TextScramble(element);
                });
            }, 2000);
        });
    }
    
    // Batch processing (Similar setup to single profile, but for batch)
    const processBatchBtn = document.getElementById('process-batch');
    if (processBatchBtn) {
        processBatchBtn.addEventListener('click', () => {
            const batchUrls = document.getElementById('batch-urls').value.trim();
            
            if (!batchUrls) {
                alert('Please enter at least one LinkedIn profile URL');
                return;
            }
            
            // Show loading spinner
            loadingSpinner.classList.remove('hidden');
            loadingMessage.textContent = 'Processing batch profiles...';
            
            // Simulate API call
            setTimeout(() => {
                // Hide loading spinner
                loadingSpinner.classList.add('hidden');
                
                // Show batch results
                document.getElementById('batch-results').classList.remove('hidden');
                
                // Create sample batch results (replace with actual API response)
                const urls = batchUrls.split('\n').filter(url => url.trim());
                const container = document.getElementById('batch-results-container');
                container.innerHTML = '';
                
                urls.slice(0, 5).forEach((url, index) => {
                    const resultCard = createBatchResultCard({
                        name: `Person ${index + 1}`,
                        company: `Company ${index + 1}`,
                        url: url
                    });
                    container.appendChild(resultCard);
                });
            }, 3000);
        });
    }
}

// Create a batch result card
function createBatchResultCard(data) {
    const card = document.createElement('div');
    card.className = 'bg-white shadow overflow-hidden sm:rounded-xl card';
    
    card.innerHTML = `
        <div class="px-5 py-4 flex justify-between items-center">
            <div>
                <h4 class="text-md font-medium text-textPrimary">${data.name}</h4>
                <p class="text-sm text-textSecondary">${data.company}</p>
            </div>
            <div class="flex space-x-2">
                <button class="view-message text-xs font-medium text-primary hover:text-primaryDark flex items-center rounded-lg px-2 py-1 hover:bg-gray-50 transition-colors">
                    <i class="fas fa-eye mr-1"></i> View
                </button>
                <button class="text-xs font-medium text-primary hover:text-primaryDark flex items-center rounded-lg px-2 py-1 hover:bg-gray-50 transition-colors">
                    <i class="fas fa-copy mr-1"></i> Copy
                </button>
                <button class="text-xs font-medium text-white bg-primary hover:bg-primaryDark flex items-center rounded-lg px-2 py-1">
                    <i class="fas fa-check mr-1"></i> Sent
                </button>
            </div>
        </div>
    `;
    
    // Add hover animation to the card
    card.classList.add('hover-scale');
    
    return card;
}

// Initialize animations and hover effects
function initAnimations() {
    // Initialize text scramble effect
    document.querySelectorAll('.scramble-text').forEach(element => {
        new TextScramble(element);
    });
    
    // Add hover listeners for animation triggers
    document.querySelectorAll('.bg-animate').forEach(element => {
        element.addEventListener('mouseenter', () => {
            element.classList.add('animate-pulse-slow');
        });
        
        element.addEventListener('mouseleave', () => {
            element.classList.remove('animate-pulse-slow');
        });
    });
}

// Text Scramble Effect (inspired by Stanford Linkd)
class TextScramble {
    constructor(el) {
        this.el = el;
        this.originalText = el.innerText;
        this.chars = '!<>-_\\/[]{}—=+*^?#________';
        this.update = this.update.bind(this);
        
        el.addEventListener('mouseenter', () => {
            this.scramble();
        });
    }
    
    scramble() {
        const originalText = this.originalText;
        const length = originalText.length;
        let iteration = 0;
        const maxIterations = 7;
        
        clearInterval(this.interval);
        
        this.interval = setInterval(() => {
            this.el.innerText = originalText
                .split('')
                .map((char, index) => {
                    if (char === ' ') return ' ';
                    
                    // If we've iterated enough for this character, show the original
                    if (index < iteration / (maxIterations / length)) {
                        return originalText[index];
                    }
                    
                    // Otherwise, show a random character
                    return this.chars[Math.floor(Math.random() * this.chars.length)];
                })
                .join('');
            
            if (iteration >= maxIterations) {
                clearInterval(this.interval);
                this.el.innerText = originalText;
            }
            
            iteration += 1;
        }, 50);
    }
    
    update() {
        let output = '';
        let complete = 0;
        
        for (let i = 0, n = this.queue.length; i < n; i++) {
            let { from, to, start, end, char } = this.queue[i];
            if (this.frame >= end) {
                complete++;
                output += to;
            } else if (this.frame >= start) {
                if (!char || Math.random() < 0.28) {
                    char = this.randomChar();
                    this.queue[i].char = char;
                }
                output += `<span class="scramble-char">${char}</span>`;
            } else {
                output += from;
            }
        }
        
        this.el.innerHTML = output;
        if (complete === this.queue.length) {
            this.resolve();
        } else {
            this.frameRequest = requestAnimationFrame(this.update);
            this.frame++;
        }
    }
    
    randomChar() {
        return this.chars[Math.floor(Math.random() * this.chars.length)];
    }
}

// Modal functionality
document.addEventListener('DOMContentLoaded', function() {
    const messageModal = document.getElementById('message-modal');
    const closeModal = document.getElementById('close-modal');
    
    if (messageModal && closeModal) {
        closeModal.addEventListener('click', () => {
            messageModal.classList.add('hidden');
        });
        
        // Close modal when clicking outside the content
        messageModal.addEventListener('click', (event) => {
            if (event.target === messageModal) {
                messageModal.classList.add('hidden');
            }
        });
        
        // Handle modal open for batch view
        document.addEventListener('click', (event) => {
            if (event.target.classList.contains('view-message') || 
                event.target.parentElement.classList.contains('view-message')) {
                
                // Set modal content (replace with actual data)
                document.getElementById('modal-person').textContent = 'Sample Person';
                document.getElementById('modal-company').textContent = 'Sample Company';
                document.getElementById('modal-message').textContent = 'This is a sample personalized message that would be generated based on the LinkedIn profile. It includes relevant details and context to make it feel genuine and thoughtful.';
                
                // Show modal
                messageModal.classList.remove('hidden');
            }
        });
    }
});

// Apply hover effects to dynamically added elements
function applyHoverEffects() {
    document.querySelectorAll('.hover-scale').forEach(element => {
        if (!element._hasHoverListener) {
            element._hasHoverListener = true;
            element.addEventListener('mouseenter', () => {
                element.style.transform = 'scale(1.05)';
                element.style.transition = 'transform 0.3s ease';
            });
            
            element.addEventListener('mouseleave', () => {
                element.style.transform = 'scale(1)';
            });
        }
    });
    
    document.querySelectorAll('.hover-glow').forEach(element => {
        if (!element._hasHoverListener) {
            element._hasHoverListener = true;
            element.addEventListener('mouseenter', () => {
                element.style.boxShadow = '0 0 15px rgba(140, 21, 21, 0.3)';
                element.style.transition = 'box-shadow 0.3s ease';
            });
            
            element.addEventListener('mouseleave', () => {
                element.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08)';
            });
        }
    });
}

// Make sure to apply hover effects whenever the DOM might change
const observer = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
        if (mutation.addedNodes.length) {
            applyHoverEffects();
        }
    });
});

// Start observing the document body for DOM changes
observer.observe(document.body, { childList: true, subtree: true });

// Initialize hover effects on page load
document.addEventListener('DOMContentLoaded', applyHoverEffects);