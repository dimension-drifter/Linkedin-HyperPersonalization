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
    // Single profile processing - Attach listeners to new buttons
    const generateConnectionBtn = document.getElementById('generate-connection');
    const generateJobInquiryBtn = document.getElementById('generate-job-inquiry');

    if (generateConnectionBtn) {
        generateConnectionBtn.addEventListener('click', () => handleGenerateRequest('connection'));
    }
    if (generateJobInquiryBtn) {
        generateJobInquiryBtn.addEventListener('click', () => handleGenerateRequest('job_inquiry'));
    }

    // Batch processing - Corrected and completed listener
    const processBatchBtn = document.getElementById('process-batch');
    const batchUrlsTextarea = document.getElementById('batch-urls');
    const batchResultsContainer = document.getElementById('batch-results-container');
    const batchResultsSection = document.getElementById('batch-results');

    if (processBatchBtn && batchUrlsTextarea && batchResultsContainer && batchResultsSection) {
        processBatchBtn.addEventListener('click', () => {
            console.log("Process Batch button clicked"); // Debug log
            const batchUrls = batchUrlsTextarea.value.trim();

            if (!batchUrls) {
                showToast('Please enter at least one LinkedIn URL for batch processing.', 'warning');
                batchUrlsTextarea.focus();
                batchUrlsTextarea.classList.add('shake-animation');
                setTimeout(() => batchUrlsTextarea.classList.remove('shake-animation'), 500);
                return;
            }

            // Parse URLs into an array, removing empty lines
            const urls = batchUrls.split('\n').map(url => url.trim()).filter(url => url);

            if (urls.length === 0) {
                showToast('No valid URLs found in the batch input.', 'warning');
                return;
            }

            if (urls.length > 5) {
                showToast(`Maximum 5 URLs allowed per batch. You entered ${urls.length}.`, 'warning');
                return;
            }

            console.log("Processing batch URLs:", urls); // Debug log

            // Show loading spinner
            const loader = showLoading(`Processing ${urls.length} profiles...`, 5);
            batchResultsSection.classList.remove('hidden'); // Show results section
            batchResultsContainer.innerHTML = ''; // Clear previous results

            // Call the API endpoint
            fetch('/api/process_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                // Ensure tech_stack is included if needed, similar to single profile
                body: JSON.stringify({
                    urls: urls,
                    tech_stack: document.getElementById('tech-stack')?.value.trim() || '' // Include tech stack if relevant for batch
                 }),
            })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => { throw new Error(err.error || `HTTP error! status: ${response.status}`) });
                }
                return response.json();
            })
            .then(data => {
                console.log("Batch processing response:", data); // Debug log
                loader.complete(`Batch processing complete!`);
                batchResultsSection.classList.remove('hidden');

                if (Array.isArray(data)) {
                    data.forEach(result => {
                        if (result.error) {
                            // Display error card
                            const errorCard = document.createElement('div');
                            errorCard.className = 'linkd-card p-4 mb-4 bg-red-50 border border-red-200';
                            errorCard.innerHTML = `
                                <p class="text-sm font-medium text-red-700">Error processing URL: ${result.url || 'Unknown URL'}</p>
                                <p class="text-xs text-red-600">${result.error}</p>
                            `;
                            batchResultsContainer.appendChild(errorCard);
                        } else {
                            // Display success card (assuming createBatchResultCard exists and handles the new structure)
                            // Adapt createBatchResultCard if needed to handle connection/job inquiry messages separately
                            // For now, let's assume it primarily uses the connection message for the card preview/actions
                            const cardData = {
                                name: result.full_name || 'N/A',
                                company: result.company_name || 'N/A',
                                // Pass both messages, let the card decide what to show/copy
                                connection_message: result.connection_message?.text || '',
                                connection_message_id: result.connection_message?.id || null,
                                job_inquiry_message: result.job_inquiry_message?.text || '',
                                job_inquiry_message_id: result.job_inquiry_message?.id || null,
                                // Decide which message ID to use for the primary "Mark Sent" if shown on card
                                message_id: result.connection_message?.id // Defaulting to connection ID for card actions
                            };
                            // Check if createBatchResultCard exists before calling
                            if (typeof createBatchResultCard === 'function') {
                                const cardElement = createBatchResultCard(cardData);
                                batchResultsContainer.appendChild(cardElement);
                            } else {
                                console.error("createBatchResultCard function not found.");
                                // Fallback display if function is missing
                                const fallbackCard = document.createElement('div');
                                fallbackCard.className = 'linkd-card p-4 mb-4';
                                fallbackCard.textContent = `Processed: ${cardData.name} at ${cardData.company}`;
                                batchResultsContainer.appendChild(fallbackCard);
                            }
                        }
                    });
                } else {
                     showToast('Received unexpected data format from batch processing.', 'error');
                }
                 // Scroll to results
                 batchResultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            })
            .catch(error => {
                console.error('Error processing batch:', error);
                loader.error(`Batch Error: ${error.message || 'Failed to process batch.'}`);
                showToast(`Batch Error: ${error.message || 'Failed to process batch.'}`, 'error');
                // Optionally hide or clear results section on error
                // batchResultsSection.classList.add('hidden');
            });
        });
    } else {
        // Log if any required elements are missing
        if (!processBatchBtn) console.error("Batch process button not found");
        if (!batchUrlsTextarea) console.error("Batch URLs textarea not found");
        if (!batchResultsContainer) console.error("Batch results container not found");
        if (!batchResultsSection) console.error("Batch results section not found");
    }

    // History tab - Load message history on tab click
    document.getElementById('tab-history')?.addEventListener('click', loadMessageHistory);

    // Resume Upload (keep existing logic)
    setupResumeUpload();
    checkExistingResume(); // Check on load

    // Settings Modal (keep existing logic)
    setupSettingsModal();
}

// NEW: Handler for both generate buttons
let isProcessingSingleProfile = false; // Prevent duplicate clicks

function handleGenerateRequest(messageType) {
    if (isProcessingSingleProfile) {
        showToast('Already processing a request...', 'warning');
        return;
    }

    const linkedinUrlInput = document.getElementById('linkedin-url');
    const techStackInput = document.getElementById('tech-stack');
    const profileResultsDiv = document.getElementById('profile-results');

    const linkedinUrl = linkedinUrlInput.value.trim();
    const techStack = techStackInput.value.trim();

    if (!linkedinUrl) {
        showToast('Please enter a LinkedIn profile URL', 'warning');
        linkedinUrlInput.focus();
        linkedinUrlInput.classList.add('shake-animation');
        setTimeout(() => linkedinUrlInput.classList.remove('shake-animation'), 500);
        return;
    }

    // Basic URL validation
    if (!linkedinUrl.toLowerCase().includes('linkedin.com/in/')) {
        showToast('Please enter a valid LinkedIn profile URL (e.g., linkedin.com/in/username)', 'warning');
        linkedinUrlInput.focus();
        linkedinUrlInput.classList.add('shake-animation');
        setTimeout(() => linkedinUrlInput.classList.remove('shake-animation'), 500);
        return;
    }

    isProcessingSingleProfile = true;
    profileResultsDiv.classList.add('hidden'); // Hide previous results

    const loaderMessage = messageType === 'connection' ? 'Generating connection request...' : 'Generating job inquiry...';
    const loader = showLoading(loaderMessage, 10);

    fetch('/api/process_profile', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            url: linkedinUrl,
            tech_stack: techStack,
            message_type: messageType // Send the requested type
        }),
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => { throw new Error(err.error || `HTTP error! status: ${response.status}`) });
        }
        return response.json();
    })
    .then(data => {
        loader.complete('Message generated successfully!');
        displayGeneratedMessage(data); // Call function to display results
        isProcessingSingleProfile = false;
    })
    .catch(error => {
        console.error('Error processing profile:', error);
        loader.error(`Error: ${error.message || 'Failed to generate message.'}`);
        showToast(`Error: ${error.message || 'Failed to generate message.'}`, 'error');
        isProcessingSingleProfile = false;
    });
}

// NEW: Function to display the generated message
function displayGeneratedMessage(data) {
    const profileResultsDiv = document.getElementById('profile-results');
    const resultNameSpan = document.getElementById('result-name');
    const messageTypeLabel = document.getElementById('message-type-label');
    const resultMessageDiv = document.getElementById('result-message');
    const charCountSpan = document.getElementById('char-count');
    const copyButton = document.getElementById('copy-message');
    const markSentButton = document.getElementById('mark-sent-message');

    if (!data || !data.message_text) {
        showToast('Received invalid data from server.', 'error');
        profileResultsDiv.classList.add('hidden');
        return;
    }

    resultNameSpan.textContent = data.full_name || 'the profile';
    resultMessageDiv.innerHTML = parseMarkdown(data.message_text); // Use parseMarkdown

    const messageLength = data.message_text.length;
    let charLimit = '';
    if (data.message_type === 'connection') {
        messageTypeLabel.textContent = 'Connection Request Message:';
        charLimit = '/ 300 chars';
        markSentButton.classList.remove('hidden'); // Show Mark Sent for connection
        markSentButton.setAttribute('data-id', data.message_id);
        // Add listener for mark sent button if not already added
        if (!markSentButton._hasListener) {
             markSentButton.addEventListener('click', handleMarkSentClick);
             markSentButton._hasListener = true;
        }
    } else if (data.message_type === 'job_inquiry') {
        messageTypeLabel.textContent = 'Job Inquiry Message:';
        charLimit = '/ ~2000 chars'; // LinkedIn message limit is higher
        markSentButton.classList.add('hidden'); // Hide Mark Sent for job inquiry
    } else {
        messageTypeLabel.textContent = 'Generated Message:';
        markSentButton.classList.add('hidden');
    }

    charCountSpan.textContent = `(${messageLength} ${charLimit})`;
    if (data.message_type === 'connection' && messageLength > 300) {
        charCountSpan.classList.add('text-red-600', 'font-semibold');
    } else {
        charCountSpan.classList.remove('text-red-600', 'font-semibold');
    }


    // Setup copy button
    copyButton.setAttribute('data-message-id', data.message_id); // Store ID if needed
    copyButton.onclick = () => {
        copyToClipboard(data.message_text);
        // Visual feedback for copy
        const originalIcon = copyButton.innerHTML;
        copyButton.innerHTML = '<i class="fas fa-check text-green-600"></i> Copied';
        copyButton.disabled = true;
        setTimeout(() => {
            copyButton.innerHTML = originalIcon;
            copyButton.disabled = false;
        }, 1500);
    };


    profileResultsDiv.classList.remove('hidden');
    profileResultsDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// NEW: Handler for the Mark Sent button in the results section
function handleMarkSentClick(event) {
    const button = event.currentTarget;
    const messageId = button.getAttribute('data-id');
    if (!messageId) {
        showToast('Cannot mark message as sent: Missing ID.', 'error');
        return;
    }

    markMessageAsSent(messageId, () => {
        showToast('Message marked as sent!', 'success');
        button.innerHTML = '<i class="fas fa-check-double"></i> Sent';
        button.disabled = true;
        button.classList.replace('linkd-btn-primary', 'linkd-btn-secondary');
        button.classList.add('opacity-70');

        // Optionally, refresh history tab if visible
        if (!document.getElementById('content-history').classList.contains('hidden')) {
            loadMessageHistory();
        }
    });
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

// Resume Upload Functionality
document.addEventListener('DOMContentLoaded', function() {
    setupResumeUpload();
    checkExistingResume();
});

function setupResumeUpload() {
    const resumeUploadForm = document.getElementById('resumeUploadForm');
    const resumeFileInput = document.getElementById('resumeFile');
    const fileNameDisplay = document.getElementById('file-name-display');

    // Update filename display when file is selected
    if (resumeFileInput) {
        resumeFileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const fileName = this.files[0].name;
                fileNameDisplay.textContent = fileName.length > 25 ? 
                    fileName.substring(0, 22) + '...' : fileName;
                fileNameDisplay.classList.add('text-indigo-600');
                fileNameDisplay.classList.add('font-medium');
            } else {
                fileNameDisplay.textContent = 'Select PDF resume';
                fileNameDisplay.classList.remove('text-indigo-600');
                fileNameDisplay.classList.remove('font-medium');
            }
        });
    }

    // Handle resume form submission
    if (resumeUploadForm) {
        resumeUploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const fileInput = document.getElementById('resumeFile');
            
            if (fileInput.files.length === 0) {
                showToast('Please select a PDF resume file', 'warning');
                return;
            }
            
            formData.append('resume', fileInput.files[0]);
            
            // Show loading animation
            const loader = showLoading('Processing your resume...', 15);
            
            fetch('/api/upload_resume', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    loader.error(data.error);
                    showToast(data.error, 'error');
                } else {
                    loader.complete('Resume processed successfully!');
                    showToast('Resume processed successfully!', 'success');
                    
                    // Update UI to show resume is active
                    updateResumeStatus(true);
                    
                    // Display extracted data if available
                    if (data.tech_stack_summary) {
                        displayResumePreview(data.tech_stack_summary);
                    }
                    
                    // Store flag in localStorage that resume is uploaded
                    localStorage.setItem('resumeUploaded', 'true');
                }
            })
            .catch(error => {
                console.error('Error uploading resume:', error);
                loader.error('Error processing resume');
                showToast('Error uploading resume. Please try again.', 'error');
            });
        });
    }
}

function checkExistingResume() {
    // Check if we have an active resume
    fetch('/api/resume_data')
        .then(response => {
            if (response.ok) {
                return response.json();
            } else if (response.status === 404) {
                // No active resume found
                return null;
            } else {
                throw new Error('Error checking resume status');
            }
        })
        .then(data => {
            if (data && !data.error) {
                // We have resume data
                updateResumeStatus(true);
                
                // Create a simplified preview from the resume data
                const skills = data.skills?.technical_skills || [];
                const skillsList = Array.isArray(skills) ? skills.join(', ') : skills;
                
                let experienceText = '';
                if (data.experience && data.experience.length > 0) {
                    const latestJob = data.experience[0];
                    experienceText = `${latestJob.title} at ${latestJob.company}`;
                }
                
                const previewData = {
                    name: data.basic_info?.full_name || '',
                    skills: skillsList,
                    experience: experienceText
                };
                
                displayResumePreview(previewData);
                
                // Update tech stack textarea if it's empty
                const techStackField = document.getElementById('tech-stack');
                if (techStackField && (!techStackField.value || techStackField.value.trim() === '')) {
                    techStackField.value = skillsList;
                }
            } else {
                // No resume data
                updateResumeStatus(false);
            }
        })
        .catch(error => {
            console.error('Error checking resume status:', error);
            // Just assume no resume for error cases
            updateResumeStatus(false);
        });
}

function updateResumeStatus(isActive) {
    const statusBadge = document.getElementById('resume-status-badge');
    const uploadContainer = document.getElementById('resume-upload-container');
    const dataPreview = document.getElementById('resume-data-preview');
    
    if (statusBadge) {
        statusBadge.classList.remove('hidden');
        
        if (isActive) {
            statusBadge.textContent = 'Resume Active';
            statusBadge.classList.add('bg-green-100', 'text-green-800');
            statusBadge.classList.remove('bg-yellow-100', 'text-yellow-800');
            
            // Show data preview if it exists
            if (dataPreview) dataPreview.classList.remove('hidden');
        } else {
            statusBadge.textContent = 'No Resume';
            statusBadge.classList.add('bg-yellow-100', 'text-yellow-800');
            statusBadge.classList.remove('bg-green-100', 'text-green-800');
            
            // Hide data preview
            if (dataPreview) dataPreview.classList.add('hidden');
        }
    }
}

function displayResumePreview(data) {
    const previewContainer = document.getElementById('resume-data-preview');
    const nameElement = document.getElementById('resume-name');
    const skillsElement = document.getElementById('resume-skills');
    const experienceElement = document.getElementById('resume-experience');
    
    if (!previewContainer) return;
    
    // Show the preview container
    previewContainer.classList.remove('hidden');
    
    // If data is a string (tech_stack_summary), parse and display it
    if (typeof data === 'string') {
        // Try to extract various parts from the text summary
        const lines = data.split('\n').filter(line => line.trim());
        
        let skillsText = '';
        let experienceText = '';
        let nameText = 'Your Resume';
        
        lines.forEach(line => {
            if (line.includes('Technical skills:')) {
                skillsText = line.split('Technical skills:')[1].trim();
            } else if (line.includes('Recent role:')) {
                experienceText = line.split('Recent role:')[1].trim();
            }
        });
        
        if (nameElement) nameElement.textContent = nameText;
        if (skillsElement) skillsElement.textContent = skillsText;
        if (experienceElement) experienceElement.textContent = experienceText;
        
    } else if (typeof data === 'object') {
        // Handle structured object data
        if (nameElement) nameElement.textContent = data.name || 'Your Resume';
        if (skillsElement) skillsElement.textContent = data.skills || '';
        if (experienceElement) experienceElement.textContent = data.experience || '';
    }
}

// Modify the process-profile button handler to indicate resume usage
const processProfileBtn = document.getElementById('process-profile');
if (processProfileBtn) {
    // Remove any existing click handlers first to prevent duplication
    processProfileBtn.onclick = null;
    
    // Set up a single click handler with debounce protection
    let isProcessing = false;
    
    processProfileBtn.onclick = function(event) {
        // Prevent multiple simultaneous submissions
        if (isProcessing) {
            console.log("Already processing a request, please wait...");
            return;
        }
        
        const linkedinUrl = document.getElementById('linkedin-url').value.trim();
        const techStack = document.getElementById('tech-stack').value.trim();
        const hasResume = localStorage.getItem('resumeUploaded') === 'true';
        
        if (!linkedinUrl) {
            showToast('Please enter a LinkedIn profile URL', 'warning');
            return;
        }
        
        // Set processing flag to prevent duplicate requests
        isProcessing = true;
        
        // Show loading animation
        const loader = showLoading('Processing LinkedIn profile...', 60);
        
        // Continue with your existing fetch request...
        fetch('/api/process_profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ linkedin_url: linkedinUrl, tech_stack: techStack })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Error ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Reset processing flag when done
            isProcessing = false;
            
            // Rest of your existing code...
        })
        .catch(error => {
            // Reset processing flag on error
            isProcessing = false;
            console.error('Error processing profile:', error);
            loader.error('Error processing profile. Please try again.');
            showToast('Error processing profile. Please try again later.', 'error');
        });
    };
}

// Settings modal functionality
document.addEventListener('DOMContentLoaded', function() {
    const settingsBtn = document.getElementById('btn-settings');
    const settingsModal = document.getElementById('settings-modal');
    const closeSettingsModal = document.getElementById('close-settings-modal');
    const closeSettingsBtn = document.getElementById('close-settings-btn');
    const clearResumeBtn = document.getElementById('clear-resume-btn');
    
    // Open settings modal
    if (settingsBtn && settingsModal) {
        settingsBtn.addEventListener('click', function() {
            // Update resume status in settings before showing
            updateSettingsResumeStatus();
            
            // Show modal
            settingsModal.classList.remove('hidden');
            settingsModal.classList.add('fade-in');
        });
    }
    
    // Close settings modal
    if (closeSettingsModal && settingsModal) {
        closeSettingsModal.addEventListener('click', function() {
            settingsModal.classList.add('hidden');
        });
    }
    
    if (closeSettingsBtn && settingsModal) {
        closeSettingsBtn.addEventListener('click', function() {
            settingsModal.classList.add('hidden');
        });
    }
    
    // Close settings modal when clicking outside content
    if (settingsModal) {
        settingsModal.addEventListener('click', function(event) {
            if (event.target === settingsModal) {
                settingsModal.classList.add('hidden');
            }
        });
    }
    
    // Handle clear resume button
    if (clearResumeBtn) {
        clearResumeBtn.addEventListener('click', function() {
            // Confirm before clearing
            if (confirm('Are you sure you want to clear your resume data? This will remove all extracted skills and experience.')) {
                // Call API to clear resume (you'll need to implement this endpoint)
                fetch('/api/clear_resume', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Failed to clear resume');
                    }
                    return response.json();
                })
                .then(data => {
                    showToast('Resume data cleared successfully', 'success');
                    localStorage.removeItem('resumeUploaded');
                    
                    // Update UI
                    updateResumeStatus(false);
                    updateSettingsResumeStatus();
                })
                .catch(error => {
                    console.error('Error clearing resume:', error);
                    showToast('Failed to clear resume. Please try again.', 'error');
                });
            }
        });
    }
});

function updateSettingsResumeStatus() {
    const resumeStatus = document.getElementById('settings-resume-status');
    
    fetch('/api/resume_data')
        .then(response => {
            if (response.ok) {
                return response.json();
            } else if (response.status === 404) {
                throw new Error('No resume found');
            } else {
                throw new Error('Error checking resume');
            }
        })
        .then(data => {
            const name = data.basic_info?.full_name || 'Your resume';
            const uploadDate = new Date().toLocaleDateString(); // Ideally from the server
            
            resumeStatus.innerHTML = `
                <span class="font-medium text-indigo-600">${name}</span> 
                <span class="text-gray-500">• Uploaded on ${uploadDate}</span>
                <div class="mt-1">
                    <span class="inline-block bg-green-100 text-green-800 text-xs px-2 py-0.5 rounded-full">
                        <i class="fas fa-check-circle mr-1"></i> Active
                    </span>
                </div>
            `;
        })
        .catch(error => {
            resumeStatus.textContent = 'No resume uploaded yet.';
        });
}
