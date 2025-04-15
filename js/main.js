// Main JavaScript for the LinkedIn tool
document.addEventListener('DOMContentLoaded', function() {
    // Tab switching functionality
    setupTabs();
    
    // Mobile menu toggle
    setupMobileMenu();
    
    // Form submission handlers
    setupFormHandlers();
    
    // Initialize animations
    initAnimations();

    // Export CSV button handler
    const exportCsvBtn = document.getElementById('export-csv');
    if (exportCsvBtn) {
        exportCsvBtn.addEventListener('click', function() {
            // Create a hidden link and trigger download
            fetch('/api/export_csv')
                .then(response => {
                    if (!response.ok) throw new Error('Failed to export CSV');
                    return response.blob();
                })
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = 'linkedin_messages.csv';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);
                })
                .catch(err => {
                    showToast('Failed to export CSV. Please try again.', 'error');
                    console.error(err);
                });
        });
    }
});

// Handle tab switching
function setupTabs() {
    const tabs = document.querySelectorAll('[role="tab"]');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active classes
            tabs.forEach(t => {
                t.setAttribute('aria-selected', 'false');
                t.classList.remove('border-primary', 'bg-white', 'shadow-sm', 'text-primary');
                t.classList.add('border-transparent');
            });
            
            // Add active class to clicked tab
            tab.setAttribute('aria-selected', 'true');
            tab.classList.add('border-primary', 'bg-white', 'shadow-sm', 'text-primary');
            tab.classList.remove('border-transparent');
            
            // Hide all tab panes
            tabPanes.forEach(pane => {
                pane.classList.add('hidden');
            });
            
            // Show corresponding tab pane
            const tabId = tab.id;
            const paneId = 'content-' + tabId.split('-')[1];
            const pane = document.getElementById(paneId);
            pane.classList.remove('hidden');
            
            // Add fade-in animation
            pane.classList.add('fade-in');
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
                showToast('Please enter a LinkedIn profile URL', 'warning');
                return;
            }
            
            // Show loading with enhanced animation
            const loader = showLoading('Analyzing LinkedIn profile...', 10);
            
            // Call the API endpoint
            fetch('/api/process_profile', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: linkedinUrl }),
            })
            .then(response => {
                loader.updateMessage('Generating personalized message...');
                loader.setProgress(60);
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                // Complete loading with success animation
                loader.complete('Message generated successfully!');
                
                // Show results
                profileResults.classList.remove('hidden');
                profileResults.classList.add('fade-in');
                
                // Populate with API response data
                document.getElementById('result-name').textContent = data.founder.full_name || 'Unknown';
                document.getElementById('result-headline').textContent = data.founder.headline || 'N/A';
                document.getElementById('result-location').textContent = data.founder.location || 'N/A';
                document.getElementById('result-company').textContent = data.company.name || 'N/A';
                document.getElementById('result-summary').innerHTML = parseMarkdown(data.summary) || 'No summary available';
                document.getElementById('result-message').innerHTML = parseMarkdown(data.message) || '';
                
                // Update character count
                const messageLength = data.message ? data.message.length : 0;
                document.getElementById('character-count').textContent = messageLength.toString();
                
                // Add message_id to the Mark Sent button
                const markSentBtn = document.querySelector('#profile-results .linkd-btn-primary');
                if (markSentBtn && data.message_id) {
                    markSentBtn.setAttribute('data-id', data.message_id);
                    
                    // Add event listener if not already added
                    if (!markSentBtn._hasListener) {
                        markSentBtn._hasListener = true;
                        markSentBtn.addEventListener('click', function() {
                            const messageId = this.getAttribute('data-id');
                            if (!messageId) {
                                showToast('Cannot mark as sent: No message ID', 'warning');
                                return;
                            }
                            
                            // Show loading state
                            const originalHtml = this.innerHTML;
                            this.innerHTML = '<i class="fas fa-spinner fa-spin mr-1.5"></i> Processing...';
                            this.disabled = true;
                            
                            markMessageAsSent(messageId, () => {
                                // Show success
                                this.innerHTML = '<i class="fas fa-check mr-1.5"></i> Marked as Sent';
                                this.classList.add('bg-green-600');
                                showToast('Message marked as sent!', 'success');
                            });
                        });
                    }
                }

                // Add copy functionality
                const copyBtn = document.querySelector('#result-copy');
                if (copyBtn) {
                    copyBtn.addEventListener('click', function() {
                        const message = document.getElementById('result-message').innerText;
                        copyToClipboard(message);
                        
                        // Show visual feedback
                        const originalHtml = this.innerHTML;
                        this.innerHTML = '<i class="fas fa-check text-green-600 mr-1.5"></i> Copied!';
                        
                        setTimeout(() => {
                            this.innerHTML = originalHtml;
                        }, 2000);
                    });
                }
            })
            .catch(error => {
                console.error('Error processing profile:', error);
                loader.error('Error processing profile. Please try again.');
                showToast('Error processing profile. Please try again later.', 'error');
            });
        });
    }
    
    // Batch processing
    const processBatchBtn = document.getElementById('process-batch');
    if (processBatchBtn) {
        processBatchBtn.addEventListener('click', () => {
            const batchUrls = document.getElementById('batch-urls').value.trim();
            
            if (!batchUrls) {
                showToast('Please enter at least one LinkedIn profile URL', 'warning');
                return;
            }
            
            // Parse URLs into an array
            const urls = batchUrls.split('\n').filter(url => url.trim());
            
            if (urls.length > 5) {
                showToast('You can process a maximum of 5 profiles at once', 'warning');
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
                const batchResults = document.getElementById('batch-results');
                batchResults.classList.remove('hidden');
                batchResults.classList.add('fade-in');
                
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
                    container.innerHTML = '<div class="bg-red-50 p-4 rounded-xl text-red-600">Error processing batch profiles</div>';
                }
            })
            .catch(error => {
                console.error('Error processing batch:', error);
                loadingSpinner.classList.add('hidden');
                showToast('Error processing batch profiles. Please try again later.', 'error');
            });
        });
    }
    
    // History tab - Load message history on tab click
    document.getElementById('tab-history')?.addEventListener('click', loadMessageHistory);
}

// Enhanced batch result card with interactive effects
function createBatchResultCard(data) {
    const card = document.createElement('div');
    card.className = 'linkd-card overflow-hidden fade-in relative';
    card.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';
    
    // Add subtle hover interaction
    card.addEventListener('mouseenter', () => {
        card.style.transform = 'translateY(-4px)';
        card.style.boxShadow = '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)';
    });
    
    card.addEventListener('mouseleave', () => {
        card.style.transform = 'translateY(0)';
        card.style.boxShadow = '0 1px 3px rgba(0, 0, 0, 0.05)';
    });
    
    card.innerHTML = `
        <div class="absolute top-0 right-0 mt-4 mr-4 opacity-0 transition-opacity duration-300" id="card-toolbar">
            <div class="bg-white rounded-lg shadow-md flex items-center p-1">
                <button class="view-message p-1.5 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors" 
                    data-message="${encodeURIComponent(data.message)}" data-name="${data.name}" data-company="${data.company}"
                    title="View full message">
                    <i class="fas fa-expand-alt"></i>
                </button>
                <button class="copy-message p-1.5 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors ml-1" 
                    data-message="${encodeURIComponent(data.message)}"
                    title="Copy to clipboard">
                    <i class="fas fa-copy"></i>
                </button>
                <button class="mark-sent p-1.5 text-indigo-600 hover:text-indigo-900 hover:bg-indigo-50 rounded-md transition-colors ml-1" 
                    data-id="${data.message_id}"
                    title="Mark as sent">
                    <i class="fas fa-check"></i>
                </button>
            </div>
        </div>

        <div class="p-5 border-b border-gray-100 flex justify-between items-center">
            <div>
                <h4 class="font-medium scramble-text">${data.name}</h4>
                <p class="text-sm text-gray-500">${data.company}</p>
            </div>
            <div class="flex space-x-2 sm:flex md:hidden lg:hidden xl:hidden">
                <button class="view-message text-xs flex items-center gap-1 text-indigo-600 hover:text-indigo-800 px-2 py-1 rounded hover:bg-indigo-50 transition-colors" data-message="${encodeURIComponent(data.message)}" data-name="${data.name}" data-company="${data.company}">
                    <i class="fas fa-eye"></i> View
                </button>
                <button class="mark-sent linkd-btn-primary text-xs px-3 py-1 rounded" data-id="${data.message_id}">
                    <i class="fas fa-check mr-1"></i> Send
                </button>
            </div>
        </div>
        <div class="p-5 bg-gray-50 hover:bg-gray-100 transition-colors">
            <div class="text-sm mb-2 text-gray-500">Message Preview:</div>
            <div class="text-sm text-gray-700 line-clamp-3 message-preview prose-sm">
                ${parseMarkdown(data.message.substring(0, 250))}${data.message.length > 250 ? '...' : ''}
            </div>
        </div>
    `;
    
    // Show toolbar on hover
    card.addEventListener('mouseenter', () => {
        const toolbar = card.querySelector('#card-toolbar');
        toolbar.classList.add('opacity-100');
    });
    
    card.addEventListener('mouseleave', () => {
        const toolbar = card.querySelector('#card-toolbar');
        toolbar.classList.remove('opacity-100');
    });
    
    // Add event listeners for buttons
    const viewButtons = card.querySelectorAll('.view-message');
    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            const message = decodeURIComponent(this.getAttribute('data-message'));
            const name = this.getAttribute('data-name');
            const company = this.getAttribute('data-company');
            const messageId = data.message_id;
            showMessageModal(name, company, message, messageId);
        });
    });
    
    card.querySelectorAll('.copy-message').forEach(button => {
        button.addEventListener('click', function() {
            const message = decodeURIComponent(this.getAttribute('data-message'));
            copyToClipboard(message);
            
            // Add visual feedback
            const originalIcon = this.innerHTML;
            this.innerHTML = '<i class="fas fa-check"></i>';
            this.classList.add('text-green-600');
            
            setTimeout(() => {
                this.innerHTML = originalIcon;
                this.classList.remove('text-green-600');
            }, 1500);
        });
    });
    
    card.querySelectorAll('.mark-sent').forEach(button => {
        if (data.message_id) {
            button.disabled = false;
            button.addEventListener('click', function() {
                const messageId = this.getAttribute('data-id');
                
                // Add loading state
                const originalHtml = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                this.disabled = true;
                
                markMessageAsSent(messageId, () => {
                    // Show success
                    this.innerHTML = '<i class="fas fa-check"></i>';
                    this.classList.add('text-green-600');
                    card.classList.add('opacity-75');
                    
                    // Add sent badge
                    const badge = document.createElement('div');
                    badge.className = 'absolute top-0 left-0 bg-green-500 text-white text-xs px-2 py-1 rounded-br-lg';
                    badge.innerHTML = '<i class="fas fa-check mr-1"></i> Sent';
                    card.appendChild(badge);
                    
                    showToast('Message marked as sent!', 'success');
                });
            });
        } else {
            button.disabled = true;
            button.classList.add('opacity-50');
        }
    });
    
    // Make message preview clickable to view full message
    const preview = card.querySelector('.message-preview');
    preview.style.cursor = 'pointer';
    preview.addEventListener('click', () => {
        const viewButton = card.querySelector('.view-message');
        viewButton.click();
    });
    
    // Initialize text scramble effect on name
    setTimeout(() => {
        const nameElement = card.querySelector('.scramble-text');
        new TextScramble(nameElement);
    }, 100);
    
    return card;
}

// Initialize animations
function initAnimations() {
    // Rerun the text scramble for all elements
    document.querySelectorAll('.scramble-text').forEach(element => {
        // Ensure initialization when elements are added dynamically
        if (!element._scramble) {
            element._scramble = new TextScramble(element);
        }
    });
}

// Enhanced Text Scramble Effect with colored characters
class TextScramble {
    constructor(el) {
        this.el = el;
        this.originalText = el.innerText;
        this.chars = '!<>-_\\/[]{}—=+*^?#________';
        this.colors = ['#4f46e5', '#6366f1', '#8b5cf6', '#d946ef', '#ec4899']; // Linkd gradient colors
        this.update = this.update.bind(this);
        
        // Add hover effects
        el.addEventListener('mouseenter', () => {
            this.scramble();
            el.style.transition = 'all 0.3s ease';
            el.style.textShadow = '0 0 8px rgba(79, 70, 229, 0.3)';
        });
        
        el.addEventListener('mouseleave', () => {
            el.style.textShadow = 'none';
        });
        
        // Store reference to this instance in the element
        el._scramble = this;
        
        // Add initial animation on page load for elements with auto-animate class
        if (el.classList.contains('auto-animate')) {
            setTimeout(() => this.scramble(), 1000 + Math.random() * 1000);
        }
    }
    
    setText(newText) {
        const oldText = this.el.innerText;
        const length = Math.max(oldText.length, newText.length);
        this.queue = [];
        
        for (let i = 0; i < length; i++) {
            const from = oldText[i] || '';
            const to = newText[i] || '';
            const start = Math.floor(Math.random() * 15); // Faster start
            const end = start + Math.floor(Math.random() * 20); // Shorter duration
            const color = this.colors[Math.floor(Math.random() * this.colors.length)];
            this.queue.push({ from, to, start, end, char: null, color });
        }
        
        cancelAnimationFrame(this.frameRequest);
        this.frame = 0;
        this.update();
        return new Promise(resolve => this.resolve = resolve);
    }
    
    update() {
        let output = '';
        let complete = 0;
        
        for (let i = 0, n = this.queue.length; i < n; i++) {
            let { from, to, start, end, char, color } = this.queue[i];
            if (this.frame >= end) {
                complete++;
                output += to;
            } else if (this.frame >= start) {
                if (!char || Math.random() < 0.28) {
                    char = this.chars[Math.floor(Math.random() * this.chars.length)];
                    this.queue[i].char = char;
                    this.queue[i].color = this.colors[Math.floor(Math.random() * this.colors.length)];
                }
                output += `<span class="scramble-char" style="color:${color}">${char}</span>`;
            } else {
                output += from;
            }
        }
        
        this.el.innerHTML = output;
        if (complete === this.queue.length) {
            this.el.innerHTML = this.originalText; // Reset to clean text
            this.resolve();
        } else {
            this.frameRequest = requestAnimationFrame(this.update);
            this.frame++;
        }
    }
    
    scramble() {
        this.setText(this.originalText);
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

        // Handle modal open for batch view (use actual data)
        document.addEventListener('click', (event) => {
            let btn = event.target;
            if (!btn.classList.contains('view-message') && btn.parentElement?.classList.contains('view-message')) {
                btn = btn.parentElement;
            }
            if (btn.classList.contains('view-message')) {
                const name = btn.getAttribute('data-name') || '-';
                const company = btn.getAttribute('data-company') || '-';
                const message = decodeURIComponent(btn.getAttribute('data-message') || '');

                document.getElementById('modal-person').textContent = name;
                document.getElementById('modal-company').textContent = company;
                document.getElementById('modal-message').innerHTML = parseMarkdown(message);

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
    historyTable.innerHTML = '<tr><td colspan="7" class="text-center py-6 text-gray-500"><div class="flex justify-center"><div class="flex space-x-2"><div class="w-2 h-2 rounded-full bg-indigo-600 loading-dot"></div><div class="w-2 h-2 rounded-full bg-indigo-600 loading-dot"></div><div class="w-2 h-2 rounded-full bg-indigo-600 loading-dot"></div></div></div><div class="mt-2">Loading message history...</div></td></tr>';
    
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
                    
                    const isSent = message.sent ? 'checked' : '';
                    const formattedDate = new Date(message.generated_date).toLocaleDateString();
                    
                    row.innerHTML = `
                        <td class="px-6 py-4 text-sm">${message.full_name}</td>
                        <td class="px-6 py-4 text-sm">${message.company_name || 'N/A'}</td>
                        <td class="px-6 py-4 text-sm">
                            <a href="${message.linkedin_url}" target="_blank" class="text-indigo-600 hover:text-indigo-800 hover:underline">
                                ${message.linkedin_url.substring(0, 24)}...
                            </a>
                        </td>
                        <td class="px-4 py-4 text-sm text-gray-500">${formattedDate}</td>
                        <td class="px-6 py-4 text-sm max-w-xs" style="max-width: 200px;">
                            <div class="truncate" title="${message.message_text}">${message.message_text || ''}</div>
                        </td>
                        <td class="px-6 py-4">
                            <input type="checkbox" ${isSent} class="linkd-checkbox mark-sent-checkbox" data-id="${message.id}">
                        </td>
                        <td class="px-6 py-4">
                            <div class="flex space-x-3">
                                <button class="text-indigo-600 hover:text-indigo-800 message-view" title="View message" data-id="${message.id}" data-name="${message.full_name}" data-company="${message.company_name}" data-message="${encodeURIComponent(message.message_text)}">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button class="text-indigo-600 hover:text-indigo-800 message-copy" title="Copy message" data-message="${encodeURIComponent(message.message_text)}">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                        </td>
                    `;
                    
                    historyTable.appendChild(row);
                });
                
                // Add event listeners for table actions
                document.querySelectorAll('.mark-sent-checkbox').forEach(checkbox => {
                    checkbox.addEventListener('change', function() {
                        const messageId = this.getAttribute('data-id');
                        if (this.checked) {
                            markMessageAsSent(messageId, () => {
                                showToast('Message marked as sent!', 'success');
                            });
                        }
                    });
                });
                
                document.querySelectorAll('.message-view').forEach(button => {
                    button.addEventListener('click', function() {
                        const name = this.getAttribute('data-name');
                        const company = this.getAttribute('data-company');
                        const message = decodeURIComponent(this.getAttribute('data-message'));
                        const messageId = this.getAttribute('data-id');
                        showMessageModal(name, company, message, messageId);
                    });
                });
                
                document.querySelectorAll('.message-copy').forEach(button => {
                    button.addEventListener('click', function() {
                        const message = decodeURIComponent(this.getAttribute('data-message'));
                        copyToClipboard(message);
                    });
                });
            } else {
                historyTable.innerHTML = '<tr><td colspan="7" class="text-center py-6 text-gray-500">No messages found.</td></tr>';
            }
        })
        .catch(error => {
            console.error('Error loading message history:', error);
            historyTable.innerHTML = '<tr><td colspan="7" class="text-center py-6 text-red-500">Error loading message history.</td></tr>';
        });
}

// Enhanced modal component
function showMessageModal(name, company, message, messageId) {
    const modal = document.getElementById('message-modal');
    if (!modal) return;
    
    // Prepare modal content
    document.getElementById('modal-person').textContent = name;
    document.getElementById('modal-company').textContent = company || 'N/A';
    document.getElementById('modal-message').innerHTML = parseMarkdown(message);
    
    // Add copy functionality to modal copy button
    document.getElementById('modal-copy').onclick = function() {
        copyToClipboard(message);
        
        // Give visual feedback
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="fas fa-check text-green-600"></i> Copied!';
        
        setTimeout(() => {
            this.innerHTML = originalText;
        }, 2000);
    };
    
    // Add mark as sent functionality with message ID
    const markSentBtn = document.getElementById('modal-mark-sent');
    if (markSentBtn) {
        // Set or update the message ID attribute
        if (messageId) {
            markSentBtn.setAttribute('data-id', messageId);
            markSentBtn.disabled = false;
            markSentBtn.classList.remove('opacity-50');
        } else {
            markSentBtn.removeAttribute('data-id');
            markSentBtn.disabled = true;
            markSentBtn.classList.add('opacity-50');
        }
        
        // Make sure we only add the event listener once
        if (!markSentBtn._hasListener) {
            markSentBtn._hasListener = true;
            markSentBtn.addEventListener('click', function() {
                const msgId = this.getAttribute('data-id');
                if (!msgId) {
                    showToast('Cannot mark as sent: No message ID found.', 'warning');
                    return;
                }
                
                // Show loading state
                const originalHtml = this.innerHTML;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                this.disabled = true;
                
                markMessageAsSent(msgId, () => {
                    // Update button to show success
                    this.innerHTML = '<i class="fas fa-check"></i> Marked as Sent';
                    this.classList.add('bg-green-600');
                    showToast('Message marked as sent!', 'success');
                    
                    // Close modal after a short delay
                    setTimeout(() => {
                        document.getElementById('close-modal').click();
                    }, 1500);
                });
            });
        }
    }
    
    // Add visual entrance animation
    modal.classList.remove('hidden');
    modal.classList.add('fade-in');
    
    // Add subtle animations to modal content
    const modalContent = modal.querySelector('.bg-white');
    modalContent.classList.add('modal-entry-animation');
    setTimeout(() => {
        const textElements = modalContent.querySelectorAll('p, h3');
        textElements.forEach((el, i) => {
            el.style.animation = `fadeSlideIn 0.3s ease forwards ${0.1 + i * 0.1}s`;
            el.style.opacity = '0';
            el.style.transform = 'translateY(10px)';
        });
    }, 100);
}

// Copy message to clipboard with improved handling
function copyToClipboard(text) {
    // If text has HTML entities or tags, create a temporary div to extract plain text
    if (text.includes('<') || text.includes('&')) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = text;
        text = tempDiv.textContent || tempDiv.innerText || '';
    }
    
    navigator.clipboard.writeText(text)
        .then(() => {
            showToast('Message copied to clipboard!', 'success');
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
                showToast('Message copied to clipboard!', 'success');
            } catch (err) {
                console.error('Fallback: Oops, unable to copy', err);
                showToast('Could not copy text. Please copy it manually.', 'error');
            }
            
            document.body.removeChild(textArea);
        });
}

// Fix missing code in markMessageAsSent function
function markMessageAsSent(messageId, callback) {
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
            if (typeof callback === 'function') callback();
        } else {
            console.error('Failed to mark message as sent');
            showToast('Failed to mark message as sent', 'error');
        }
    })
    .catch(error => {
        console.error('Error marking message as sent:', error);
        showToast('Error marking message as sent', 'error');
    });
}

// Function to show toast messages
function showToast(message, type = 'info') {
    // Remove any existing toasts
    const existingToast = document.getElementById('toast');
    if (existingToast) {
        existingToast.remove();
    }
    
    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'fixed bottom-4 right-4 z-50';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'rounded-lg py-3 px-4 shadow-lg flex items-center gap-2 fade-in';
    
    // Set icon and styles based on type
    let icon, bgColor, textColor;
    switch (type) {
        case 'success':
            icon = '<i class="fas fa-check-circle"></i>';
            bgColor = 'bg-green-50';
            textColor = 'text-green-800';
            break;
        case 'error':
            icon = '<i class="fas fa-exclamation-circle"></i>';
            bgColor = 'bg-red-50';
            textColor = 'text-red-800';
            break;
        case 'warning':
            icon = '<i class="fas fa-exclamation-triangle"></i>';
            bgColor = 'bg-yellow-50';
            textColor = 'text-yellow-800';
            break;
        default:
            icon = '<i class="fas fa-info-circle"></i>';
            bgColor = 'bg-blue-50';
            textColor = 'text-blue-800';
    }
    
    toast.className += ` ${bgColor} ${textColor}`;
    toast.innerHTML = `${icon} <span>${message}</span>`;
    
    // Add close button
    const closeBtn = document.createElement('button');
    closeBtn.className = 'ml-auto text-gray-400 hover:text-gray-600';
    closeBtn.innerHTML = '<i class="fas fa-times"></i>';
    closeBtn.onclick = () => toast.remove();
    toast.appendChild(closeBtn);
    
    // Add to container
    toastContainer.appendChild(toast);
    
    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Enhanced loading component with Linkd-style animation
function showLoading(message = 'Processing...', initialProgress = 10) {
    const loadingSpinner = document.getElementById('loading-spinner');
    const loadingMessage = document.getElementById('loading-message');
    const loadingProgress = document.getElementById('loading-progress');
    
    // Reset and show loading UI
    loadingSpinner.classList.remove('hidden');
    loadingMessage.innerHTML = `<span class="text-gradient">${message}</span>`;
    loadingProgress.style.width = `${initialProgress}%`;
    
    // Simulated progress with natural-looking increments
    let progress = initialProgress;
    let interval;
    
    const advanceProgress = () => {
        clearInterval(interval);
        
        interval = setInterval(() => {
            // Advance progress randomly but slow down near completion
            if (progress < 70) {
                progress += Math.random() * 5 + 1; // Faster initially
            } else if (progress < 90) {
                progress += Math.random() * 2; // Slower in the middle
            } else if (progress < 95) {
                progress += Math.random() * 0.5; // Very slow at the end
            }
            
            if (progress >= 95) {
                clearInterval(interval);
                progress = 95; // Cap at 95% until complete is called
            }
            
            // Apply with smooth animation
            loadingProgress.style.width = `${progress}%`;
        }, 600);
    };
    
    advanceProgress();
    
    // Return control methods
    return {
        // Update loading message
        updateMessage: (newMessage) => {
            loadingMessage.innerHTML = `<span class="text-gradient">${newMessage}</span>`;
        },
        
        // Set progress to specific percentage
        setProgress: (percent) => {
            clearInterval(interval);
            progress = Math.min(Math.max(percent, 0), 95); // Keep below 100% until complete
            loadingProgress.style.width = `${progress}%`;
            advanceProgress();
        },
        
        // Complete loading animation
        complete: (successMessage = 'Complete!') => {
            clearInterval(interval);
            
            // Pulse animation on message
            loadingMessage.classList.add('pulse-animation');
            loadingMessage.innerHTML = `<span class="text-gradient">${successMessage}</span>`;
            
            // Complete progress bar with smooth animation
            loadingProgress.style.transition = 'width 0.5s ease-out';
            loadingProgress.style.width = '100%';
            
            // Display success animation
            setTimeout(() => {
                // Hide loading spinner with fade-out
                loadingSpinner.classList.add('fade-out');
                
                // Remove after animation completes
                setTimeout(() => {
                    loadingSpinner.classList.add('hidden');
                    loadingSpinner.classList.remove('fade-out');
                    loadingMessage.classList.remove('pulse-animation');
                    loadingProgress.style.width = '0';
                }, 500);
            }, 800);
        },
        
        // Show error state
        error: (errorMessage = 'An error occurred') => {
            clearInterval(interval);
            
            // Change progress bar to error state
            loadingProgress.classList.remove('bg-gradient-to-r', 'from-indigo-600', 'to-purple-600');
            loadingProgress.classList.add('bg-red-500');
            loadingProgress.style.width = '100%';
            
            // Update message with error
            loadingMessage.innerHTML = `<span class="text-red-600">${errorMessage}</span>`;
            loadingMessage.classList.add('shake-animation');
            
            // Hide after delay
            setTimeout(() => {
                loadingSpinner.classList.add('fade-out');
                
                setTimeout(() => {
                    loadingSpinner.classList.add('hidden');
                    loadingSpinner.classList.remove('fade-out');
                    loadingMessage.classList.remove('shake-animation');
                    loadingProgress.classList.remove('bg-red-500');
                    loadingProgress.classList.add('bg-gradient-to-r', 'from-indigo-600', 'to-purple-600');
                    loadingProgress.style.width = '0';
                }, 500);
            }, 2000);
        }
    };
}

// Add this function to parse basic markdown to HTML
function parseMarkdown(text) {
    if (!text) return '';
    
    // Handle headers
    text = text.replace(/### (.*?)(\n|$)/g, '<h3 class="text-md font-semibold mt-3 mb-1">$1</h3>');
    text = text.replace(/## (.*?)(\n|$)/g, '<h2 class="text-lg font-semibold mt-4 mb-2">$1</h2>');
    text = text.replace(/# (.*?)(\n|$)/g, '<h1 class="text-xl font-semibold mt-4 mb-3">$1</h1>');
    
    // Handle bold
    text = text.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold">$1</strong>');
    
    // Handle italic
    text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
    text = text.replace(/_(.*?)_/g, '<em>$1</em>');
    
    // Handle lists
    text = text.replace(/^\s*\*\s+(.*?)(\n|$)/gm, '<li class="ml-4">• $1</li>');
    text = text.replace(/^\s*-\s+(.*?)(\n|$)/gm, '<li class="ml-4">• $1</li>');
    text = text.replace(/^\s*\d+\.\s+(.*?)(\n|$)/gm, '<li class="ml-4 list-decimal">$1</li>');
    
    // Handle paragraphs
    text = text.replace(/\n\n/g, '</p><p class="mb-2">');
    
    // Wrap lists
    text = text.replace(/<li class="ml-4">(.+?)(?=<\/p>|$)/g, '<ul class="my-2">$&</ul>');
    text = text.replace(/<li class="ml-4 list-decimal">(.+?)(?=<\/p>|$)/g, '<ol class="my-2 list-decimal list-inside">$&</ol>');
    
    // Fix any duplicate or nested list tags
    text = text.replace(/<\/ul><ul class="my-2">/g, '');
    text = text.replace(/<\/ol><ol class="my-2 list-decimal list-inside">/g, '');
    
    // Wrap with paragraph tags if not already
    if (!text.startsWith('<p')) {
        text = '<p class="mb-2">' + text;
    }
    if (!text.endsWith('</p>')) {
        text = text + '</p>';
    }
    
    return text;
}