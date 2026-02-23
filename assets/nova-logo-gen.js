const fs = require('fs');

// Perfect macOS squircle superellipse path for a 1024x1024 canvas with proper margins
// To avoid cutting off the edges, we draw it at 960x960 centered in 1024x1024 (32px padding)
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <defs>
    <!-- Dark glassmorphism gradient -->
    <linearGradient id="bg-grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1E1E24" />
      <stop offset="50%" stop-color="#0B0B0D" />
      <stop offset="100%" stop-color="#050505" />
    </linearGradient>

    <!-- Star core bright glow -->
    <radialGradient id="star-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="1" />
      <stop offset="20%" stop-color="#D6E0FF" stop-opacity="0.9" />
      <stop offset="60%" stop-color="#6E85F7" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#4B61D1" stop-opacity="0" />
    </radialGradient>

    <!-- Edge highlight for the squircle (glass effect) -->
    <linearGradient id="glass-edge" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.3" />
      <stop offset="30%" stop-color="#FFFFFF" stop-opacity="0.05" />
      <stop offset="70%" stop-color="#000000" stop-opacity="0.1" />
      <stop offset="100%" stop-color="#000000" stop-opacity="0.8" />
    </linearGradient>

    <!-- Drop shadow for the central star -->
    <filter id="drop-shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="15" />
      <feOffset dx="0" dy="10" result="offsetblur" />
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.5" />
      </feComponentTransfer>
      <feMerge> 
        <feMergeNode />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <filter id="blur-ring">
      <feGaussianBlur stdDeviation="4" />
    </filter>
  </defs>

  <!-- macOS Squircle Background (Centered, 32px padding, 960x960 bounds) -->
  <!-- Using a standard path for an iOS/macOS icon with continuous corners -->
  <path d="M512 32 
           C295.5 32 153.2 32 87.6 97.6 
           C22 163.2 22 305.5 22 512 
           C22 718.5 22 860.8 87.6 926.4 
           C153.2 992 295.5 992 512 992 
           C728.5 992 870.8 992 936.4 926.4 
           C1002 860.8 1002 718.5 1002 512 
           C1002 305.5 1002 163.2 936.4 97.6 
           C870.8 32 728.5 32 512 32 Z" 
        fill="url(#bg-grad)" 
        stroke="url(#glass-edge)" stroke-width="3" />

  <!-- Outer Sound/Orbit Ring -->
  <circle cx="512" cy="512" r="320" fill="none" stroke="#6E85F7" stroke-width="2" stroke-opacity="0.3" />
  <circle cx="512" cy="512" r="320" fill="none" stroke="#8CA0FF" stroke-width="6" stroke-opacity="0.15" filter="url(#blur-ring)" />
  
  <!-- Dashed Orbit Ring -->
  <circle cx="512" cy="512" r="240" fill="none" stroke="#FFFFFF" stroke-width="1.5" stroke-opacity="0.4" stroke-dasharray="12 24" />

  <!-- The Nøva / Spark (4-pointed star, completely mathematical and symmetrical) -->
  <g filter="url(#drop-shadow)">
    <!-- Base large glow -->
    <path d="M512 180 
             C530 460 460 530 844 512 
             C460 494 530 564 512 844 
             C494 564 564 494 180 512 
             C564 530 494 460 512 180 Z" 
          fill="url(#star-glow)" />
          
    <!-- Sharp inner core -->
    <path d="M512 220 
             C520 480 480 520 804 512 
             C480 504 520 544 512 804 
             C504 544 544 504 220 512 
             C544 520 504 480 512 220 Z" 
          fill="#FFFFFF" />
          
    <!-- Ultra sharp crosshairs -->
    <path d="M512 140 L514 512 L512 884 L510 512 Z" fill="#FFFFFF" fill-opacity="0.8" />
    <path d="M140 512 L512 514 L884 512 L512 510 Z" fill="#FFFFFF" fill-opacity="0.8" />
  </g>
  
  <!-- Center dot -->
  <circle cx="512" cy="512" r="16" fill="#FFFFFF" />
</svg>`;

fs.writeFileSync('/Users/jl.moreno/Documents/Proyectos/Personales/whisper-meetings/assets/nova-icon-perfect.svg', svg);
console.log('SVG written');
