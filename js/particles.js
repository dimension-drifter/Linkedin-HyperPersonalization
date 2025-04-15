// Particle animation effect similar to Linkd
// Remove any existing canvas to avoid duplicates
const oldCanvas = document.getElementById('linkd-particles-canvas');
if (oldCanvas) oldCanvas.remove();

document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.createElement('canvas');
    canvas.id = 'linkd-particles-canvas';
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100vw';
    canvas.style.height = '100vh';
    canvas.style.pointerEvents = 'none';
    canvas.style.zIndex = '0'; // Lower z-index for background
    canvas.style.opacity = '1'; // Full opacity for visibility
    // Insert as first child so it's behind everything
    document.body.insertBefore(canvas, document.body.firstChild);
    
    const ctx = canvas.getContext('2d');
    
    // Make the canvas responsive and set both style and attribute
    function resizeCanvas() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        canvas.style.width = window.innerWidth + 'px';
        canvas.style.height = window.innerHeight + 'px';
    }
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    
    // Particle class
    class Particle {
        constructor() {
            this.reset();
        }
        
        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = Math.random() * 3 + 1;
            this.speedX = (Math.random() - 0.5) * 0.3;
            this.speedY = (Math.random() - 0.5) * 0.3;
            this.opacity = Math.random() * 0.7 + 0.3; // Higher alpha for visibility
            const colors = ['79, 70, 229', '139, 92, 246', '236, 72, 153', '59, 130, 246'];
            this.color = colors[Math.floor(Math.random() * colors.length)];
        }
        
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) {
                this.reset();
            }
            if (Math.random() > 0.99) {
                this.speedX += (Math.random() - 0.5) * 0.01;
                this.speedY += (Math.random() - 0.5) * 0.01;
            }
            this.speedX = Math.max(Math.min(this.speedX, 0.5), -0.5);
            this.speedY = Math.max(Math.min(this.speedY, 0.5), -0.5);
        }
        
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${this.color}, ${this.opacity})`;
            ctx.fill();
        }
    }
    
    // Create particles
    let particleCount = Math.min(Math.floor(window.innerWidth / 10), 100);
    let particles = [];
    function createParticles() {
        particleCount = Math.min(Math.floor(window.innerWidth / 10), 100);
        particles = [];
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }
    }
    createParticles();
    window.addEventListener('resize', createParticles);
    
    // Connection line between particles
    function drawLines() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                if (distance < 120) {
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(79, 70, 229, ${0.18 * (1 - distance / 120)})`;
                    ctx.lineWidth = 0.7;
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
    }
    
    // Animation loop
    function animate() {
        requestAnimationFrame(animate);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(particle => {
            particle.update();
            particle.draw();
        });
        drawLines();
    }
    animate();
    
    // Add interaction with mouse
    let mouse = {
        x: null,
        y: null,
        radius: 150
    };
    window.addEventListener('mousemove', function(event) {
        mouse.x = event.x;
        mouse.y = event.y;
    });
    const originalUpdate = Particle.prototype.update;
    Particle.prototype.update = function() {
        originalUpdate.call(this);
        if (mouse.x !== null && mouse.y !== null) {
            const dx = this.x - mouse.x;
            const dy = this.y - mouse.y;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < mouse.radius) {
                const angle = Math.atan2(dy, dx);
                const force = (mouse.radius - distance) / mouse.radius;
                this.x += Math.cos(angle) * force * 1;
                this.y += Math.sin(angle) * force * 1;
            }
        }
    };
});