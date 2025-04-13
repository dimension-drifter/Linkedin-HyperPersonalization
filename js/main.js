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
    const loadingProgress = document.getElementById('loading-progress');
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
            
            // Set initial progress
            loadingProgress.style.width = '10%';
            
            // Call the API endpoint
            fetch('/api/process_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: linkedinUrl }),
            })
            .then(response => {
                loadingProgress.style.width = '60%';
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Hide loading spinner
                loadingSpinner.classList.add('hidden');
                loadingProgress.style.width = '100%';
                
                // Show results
                profileResults.classList.remove('hidden');
                
                // Populate with API response data
                document.getElementById('result-name').textContent = data.founder.full_name || 'Unknown';
                document.getElementById('result-headline').textContent = data.founder.headline || 'N/A';
                document.getElementById('result-location').textContent = data.founder.location || 'N/A';
                document.getElementById('result-company').textContent = data.company.name || 'N/A';
                document.getElementById('result-summary').textContent = data.summary || 'No summary available';
                document.getElementById('result-message').textContent = data.message || '';
                
                // Update character count
                const messageLength = data.message ? data.message.length : 0;
                document.getElementById('character-count').textContent = messageLength.toString();
                
                // Apply text scramble effect to new content
                document.querySelectorAll('.scramble-text').forEach(element => {
                    new TextScramble(element);
                });
            })
            .catch(error => {
                console.error('Error processing profile:', error);
                loadingSpinner.classList.add('hidden');
                alert('Error processing profile. Please try again later.');
            });
        });
    }
    
    // Batch processing
    const processBatchBtn = document.getElementById('process-batch');
    if (processBatchBtn) {
        processBatchBtn.addEventListener('click', () => {
            const batchUrls = document.getElementById('batch-urls').value.trim();
            
            if (!batchUrls) {
                alert('Please enter at least one LinkedIn profile URL');
                return;
            }
            
            // Parse URLs into an array
            const urls = batchUrls.split('\n').filter(url => url.trim());
            
            if (urls.length > 5) {
                alert('You can process a maximum of 5 profiles at once');
                return;
            }
            
            // Show loading spinner
            loadingSpinner.classList.remove('hidden');
            loadingMessage.textContent = 'Processing batch profiles...';
            loadingProgress.style.width = '10%';
            
            // Call the API endpoint
            fetch('/api/process_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ urls: urls }),
            })
            .then(response => {
                loadingProgress.style.width = '70%';
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Hide loading spinner
                loadingSpinner.classList.add('hidden');
                loadingProgress.style.width = '100%';
                
                // Show batch results
                document.getElementById('batch-results').classList.remove('hidden');
                
                // Create batch results cards
                const container = document.getElementById('batch-results-container');
                container.innerHTML = '';
                
                if (Array.isArray(data)) {
                    data.forEach(result => {
                        const resultCard = createBatchResultCard({
                            name: result.founder.full_name || 'Unknown',
                            company: result.company.name || 'N/A',
                            url: result.founder.linkedin_url || '#',
                            message: result.message || '',
                            message_id: result.message_id || null
                        });
                        container.appendChild(resultCard);
                    });
                } else {
                    // Handle case where API returns a single result or error object
                    container.innerHTML = '<div class="bg-red-50 p-4 rounded-xl">Error processing batch profiles</div>';
                }
                
                // Apply hover effects to new elements
                applyHoverEffects();
            })
            .catch(error => {
                console.error('Error processing batch:', error);
                loadingSpinner.classList.add('hidden');
                alert('Error processing batch profiles. Please try again later.');
            });
        });
    }
    
    // History tab - Load message history on tab click
    document.getElementById('tab-history')?.addEventListener('click', loadMessageHistory);
}

// Create a batch result card with actual data
function createBatchResultCard(data) {
    const card = document.createElement('div');
    card.className = 'bg-white shadow overflow-hidden sm:rounded-xl card mb-4';
    
    card.innerHTML = `
        <div class="px-5 py-4 flex justify-between items-center">
            <div>
                <h4 class="text-md font-medium text-textPrimary">${data.name}</h4>
                <p class="text-sm text-textSecondary">${data.company}</p>
            </div>
            <div class="flex space-x-2">
                <button class="view-message text-xs font-medium text-primary hover:text-primaryDark flex items-center rounded-lg px-2 py-1 hover:bg-gray-50 transition-colors" data-message="${encodeURIComponent(data.message)}" data-name="${data.name}" data-company="${data.company}">
                    <i class="fas fa-eye mr-1"></i> View
                </button>
                <button class="copy-message text-xs font-medium text-primary hover:text-primaryDark flex items-center rounded-lg px-2 py-1 hover:bg-gray-50 transition-colors" data-message="${encodeURIComponent(data.message)}">
                    <i class="fas fa-copy mr-1"></i> Copy
                </button>
                <button class="mark-sent text-xs font-medium text-white bg-primary hover:bg-primaryDark flex items-center rounded-lg px-2 py-1" data-id="${data.message_id}">
                    <i class="fas fa-check mr-1"></i> Mark Sent
                </button>
            </div>
        </div>
    `;
    
    // Add event listeners for buttons
    card.querySelector('.view-message').addEventListener('click', function() {
        const message = decodeURIComponent(this.getAttribute('data-message'));
        const name = this.getAttribute('data-name');
        const company = this.getAttribute('data-company');
        showMessageModal(name, company, message);
    });
    
    card.querySelector('.copy-message').addEventListener('click', function() {
        const message = decodeURIComponent(this.getAttribute('data-message'));
        copyToClipboard(message);
    });
    
    if (data.message_id) {
        card.querySelector('.mark-sent').addEventListener('click', function() {
            const messageId = this.getAttribute('data-id');
            markMessageAsSent(messageId);
        });
    } else {
        card.querySelector('.mark-sent').disabled = true;
        card.querySelector('.mark-sent').classList.add('opacity-50');
    }
    
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

// Load message history from the API
function loadMessageHistory() {
    const historyTable = document.getElementById('history-table-body');
    if (!historyTable) return;
    
    // Show loading state
    historyTable.innerHTML = '<tr><td colspan="6" class="text-center py-4">Loading message history...</td></tr>';
    
    // Call the API endpoint
    fetch('/api/message_history')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            // Clear loading state
            historyTable.innerHTML = '';
            
            if (Array.isArray(data) && data.length > 0) {
                data.forEach(message => {
                    const row = document.createElement('tr');
                    row.className = 'hover:bg-gray-50';
                    
                    const isSent = message.sent ? 'checked' : '';
                    const formattedDate = new Date(message.generated_date).toLocaleString();
                    
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap">${message.full_name}</td>
                        <td class="px-6 py-4 whitespace-nowrap">${message.company_name || 'N/A'}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <a href="${message.linkedin_url}" target="_blank" class="text-primary hover:underline">
                                ${message.linkedin_url.substring(0, 30)}...
                            </a>
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">${formattedDate}</td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <input type="checkbox" ${isSent} class="mark-sent-checkbox" data-id="${message.id}">
                        </td>
                        <td class="px-6 py-4 whitespace-nowrap">
                            <button class="text-primary hover:text-primaryDark message-view" data-id="${message.id}" data-name="${message.full_name}" data-company="${message.company_name}" data-message="${encodeURIComponent(message.message_text)}">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="ml-2 text-primary hover:text-primaryDark message-copy" data-message="${encodeURIComponent(message.message_text)}">
                                <i class="fas fa-copy"></i>
                            </button>
                        </td>
                    `;
                    
                    historyTable.appendChild(row);
                });
                
                // Add event listeners for table actions
                document.querySelectorAll('.mark-sent-checkbox').forEach(checkbox => {
                    checkbox.addEventListener('change', function() {
                        const messageId = this.getAttribute('data-id');
                        if (this.checked) {
                            markMessageAsSent(messageId);
                        }
                    });
                });
                
                document.querySelectorAll('.message-view').forEach(button => {
                    button.addEventListener('click', function() {
                        const name = this.getAttribute('data-name');
                        const company = this.getAttribute('data-company');
                        const message = decodeURIComponent(this.getAttribute('data-message'));
                        showMessageModal(name, company, message);
                    });
                });
                
                document.querySelectorAll('.message-copy').forEach(button => {
                    button.addEventListener('click', function() {
                        const message = decodeURIComponent(this.getAttribute('data-message'));
                        copyToClipboard(message);
                    });
                });
            } else {
                historyTable.innerHTML = '<tr><td colspan="6" class="text-center py-4">No messages found.</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error loading message history:', error);
            historyTable.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-red-500">Error loading message history.</td></tr>';
        });
}

// Show message in modal
function showMessageModal(name, company, message) {
    const modal = document.getElementById('message-modal');
    if (modal) {
        document.getElementById('modal-person').textContent = name;
        document.getElementById('modal-company').textContent = company || 'N/A';
        document.getElementById('modal-message').textContent = message;
        
        // Add copy functionality to modal copy button
        document.getElementById('modal-copy').onclick = function() {
            copyToClipboard(message);
        };
        
        modal.classList.remove('hidden');
    }
}

// Copy message to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text)
        .then(() => {
            alert('Message copied to clipboard!');
        })
        .catch(err => {
            console.error('Could not copy text: ', err);
            
            // Fallback copy method
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            
            try {
                document.execCommand('copy');
                alert('Message copied to clipboard!');
            } catch (err) {
                console.error('Fallback: Oops, unable to copy', err);
                alert('Could not copy text. Please copy it manually.');
            }
            
            document.body.removeChild(textArea);
        });
}

// Mark message as sent
function markMessageAsSent(messageId) {
    if (!messageId) return;
    
    fetch('/api/mark_sent', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message_id: messageId }),
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            console.log('Message marked as sent successfully');
        } else {
            console.error('Failed to mark message as sent');
        }
    })
    .catch(error => {
        console.error('Error marking message as sent:', error);
    });
}