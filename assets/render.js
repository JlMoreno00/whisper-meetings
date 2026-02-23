const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1024, height: 1024 }
  });
  
  const svgContent = fs.readFileSync('/Users/jl.moreno/Documents/Proyectos/Personales/whisper-meetings/assets/nova-icon-perfect.svg', 'utf8');
  
  // Set HTML with no margins and transparent body
  await page.setContent(`
    <!DOCTYPE html>
    <html>
      <head>
        <style>
          body { margin: 0; padding: 0; background: transparent; overflow: hidden; }
          svg { display: block; }
        </style>
      </head>
      <body>
        ${svgContent}
      </body>
    </html>
  `);
  
  await page.screenshot({ 
    path: '/Users/jl.moreno/Documents/Proyectos/Personales/whisper-meetings/assets/nova-icon-final.png',
    omitBackground: true,
    clip: { x: 0, y: 0, width: 1024, height: 1024 }
  });
  
  await browser.close();
  console.log('Rendered perfect PNG');
})();
