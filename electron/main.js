const { app, BrowserWindow, ipcMain, screen } = require('electron');
const path = require('path');
const { spawn, execFile } = require('child_process');
const net = require('net');

// Prevent crash on broken stdout/stderr pipe (EIO)
process.stdout.on('error', () => {});
process.stderr.on('error', () => {});

let mainWindow = null;
let pythonProcess = null;
let backendStartPromise = null;

const isDev = process.argv.includes('--dev');
const PYTHON_WS_PORT = 8766;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: '#000000',
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 12, y: 12 },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function findPythonPath() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, '.venv', 'bin', 'python');
  }

  const projectRoot = path.join(__dirname, '..');
  return path.join(projectRoot, '.venv', 'bin', 'python');
}

function canConnectBackend(timeoutMs = 400) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: '127.0.0.1', port: PYTHON_WS_PORT });
    let done = false;
    const finish = (ok) => {
      if (done) return;
      done = true;
      socket.destroy();
      resolve(ok);
    };

    socket.setTimeout(timeoutMs);
    socket.once('connect', () => finish(true));
    socket.once('timeout', () => finish(false));
    socket.once('error', () => finish(false));
  });
}

function startPythonBackend() {
  return new Promise((resolve, reject) => {
    const pythonPath = findPythonPath();
    const serverModule = 'whisper_meetings.server';
    const projectRoot = path.join(__dirname, '..');
    const pyModulePath = app.isPackaged
      ? path.join(process.resourcesPath, 'src')
      : path.join(projectRoot, 'src');

    const inheritedPythonPath = process.env.PYTHONPATH;
    const pythonPathEnv = inheritedPythonPath
      ? `${pyModulePath}:${inheritedPythonPath}`
      : pyModulePath;

    let settled = false;
    const startupTimeout = setTimeout(() => {
      if (!settled) {
        settled = true;
        clearInterval(readinessProbe);
        reject(new Error('Python backend startup timed out'));
      }
    }, 15000);

    const readinessProbe = setInterval(() => {
      if (settled) {
        clearInterval(readinessProbe);
        return;
      }
      const socket = net.createConnection({ host: '127.0.0.1', port: PYTHON_WS_PORT });
      socket.once('connect', () => {
        socket.destroy();
        if (!settled) {
          settled = true;
          clearTimeout(startupTimeout);
          clearInterval(readinessProbe);
          resolve();
        }
      });
      socket.once('error', () => {
        socket.destroy();
      });
    }, 250);

    canConnectBackend().then((alreadyUp) => {
      if (alreadyUp && !settled) {
        settled = true;
        clearTimeout(startupTimeout);
        clearInterval(readinessProbe);
        resolve();
        return;
      }

      pythonProcess = spawn(pythonPath, ['-u', '-m', serverModule], {
        cwd: app.isPackaged ? process.resourcesPath : projectRoot,
        env: {
          ...process.env,
          WS_PORT: String(PYTHON_WS_PORT),
          PYTHONPATH: pythonPathEnv,
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['pipe', 'pipe', 'pipe'],
      });

      pythonProcess.stdout.on('data', (data) => {
        const msg = data.toString().trim();
        if (msg) console.log(`[python] ${msg}`);
        if (!settled && msg.includes('websocket server listening')) {
          settled = true;
          clearTimeout(startupTimeout);
          clearInterval(readinessProbe);
          resolve();
        }
      });

      pythonProcess.stderr.on('data', (data) => {
        const msg = data.toString().trim();
        if (msg) console.error(`[python] ${msg}`);
      });

      pythonProcess.on('error', (err) => {
        if (!settled) {
          settled = true;
          clearTimeout(startupTimeout);
          clearInterval(readinessProbe);
          reject(err);
        }
      });

      pythonProcess.on('exit', async (code) => {
        console.log(`[python] exited with code ${code}`);
        if (!settled) {
          const reachable = await canConnectBackend();
          if (reachable) {
            settled = true;
            clearTimeout(startupTimeout);
            clearInterval(readinessProbe);
            resolve();
          } else {
            settled = true;
            clearTimeout(startupTimeout);
            clearInterval(readinessProbe);
            reject(new Error(`Python backend exited early with code ${code}`));
          }
        }
        pythonProcess = null;
      });
    });
  });
}

async function ensureBackendRunning() {
  if (pythonProcess) {
    return;
  }
  const reachable = await canConnectBackend();
  if (reachable) {
    return;
  }
  if (!backendStartPromise) {
    backendStartPromise = startPythonBackend().finally(() => {
      backendStartPromise = null;
    });
  }
  return backendStartPromise;
}

function stopPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
}

ipcMain.handle('get-ws-port', () => PYTHON_WS_PORT);

const SUPPORTED_AUDIO_EXTS = new Set(['.mp3', '.wav', '.m4a', '.mp4', '.flac', '.ogg', '.webm']);

function getAudioDuration(filePath) {
  return new Promise((resolve) => {
    execFile('ffprobe', [
      '-v', 'quiet',
      '-show_entries', 'format=duration',
      '-of', 'csv=p=0',
      filePath,
    ], (err, stdout) => {
      if (err) return resolve(0);
      const secs = parseFloat(stdout.trim());
      resolve(Number.isFinite(secs) ? secs : 0);
    });
  });
}

let activeTranscribeProc = null;

ipcMain.handle('cancel-transcription', () => {
  if (activeTranscribeProc) {
    activeTranscribeProc.kill('SIGTERM');
    activeTranscribeProc = null;
    return { cancelled: true };
  }
  return { cancelled: false };
});

ipcMain.handle('transcribe-file', async (event, filePath) => {
  const ext = path.extname(filePath).toLowerCase();
  if (!SUPPORTED_AUDIO_EXTS.has(ext)) {
    return { success: false, error: `Formato no soportado: ${ext}` };
  }

  const durationSecs = await getAudioDuration(filePath);
  event.sender.send('transcribe-progress', { phase: 'started', durationSecs });

  const pythonPath = findPythonPath();
  const projectRoot = path.join(__dirname, '..');
  const pyModulePath = app.isPackaged
    ? path.join(process.resourcesPath, 'src')
    : path.join(projectRoot, 'src');

  const inheritedPythonPath = process.env.PYTHONPATH;
  const pythonPathEnv = inheritedPythonPath
    ? `${pyModulePath}:${inheritedPythonPath}`
    : pyModulePath;

  return new Promise((resolve) => {
    const args = ['-u', '-m', 'whisper_meetings.cli', filePath];
    const proc = spawn(pythonPath, args, {
      cwd: app.isPackaged ? process.resourcesPath : projectRoot,
      env: {
        ...process.env,
        PYTHONPATH: pythonPathEnv,
        PYTHONUNBUFFERED: '1',
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    activeTranscribeProc = proc;
    let stderr = '';
    let outputPath = '';

    proc.stderr.on('data', (data) => {
      const msg = data.toString();
      stderr += msg;
      // Parse status messages for output path
      const match = msg.match(/Output saved to (.+)/);
      if (match) {
        outputPath = match[1].trim();
      }
    });

    proc.on('error', (err) => {
      activeTranscribeProc = null;
      event.sender.send('transcribe-progress', { phase: 'error' });
      resolve({ success: false, error: err.message });
    });

    proc.on('exit', (code, signal) => {
      activeTranscribeProc = null;
      if (signal === 'SIGTERM') {
        event.sender.send('transcribe-progress', { phase: 'cancelled' });
        resolve({ success: false, error: 'cancelled' });
        return;
      }
      event.sender.send('transcribe-progress', { phase: 'done' });
      if (code === 0) {
        resolve({ success: true, outputPath });
      } else {
        // Extract meaningful error from stderr
        const lines = stderr.trim().split('\n');
        const errorLine = lines.find((l) => l.startsWith('Error:')) || lines[lines.length - 1] || 'Transcription failed';
        resolve({ success: false, error: errorLine });
      }
    });
  });
});


// --- Programmatic window dragging (bypass app-region CSS issues) ---
let dragOffset = null;

ipcMain.on('window-start-drag', () => {
  if (!mainWindow) return;
  const cursor = screen.getCursorScreenPoint();
  const [winX, winY] = mainWindow.getPosition();
  dragOffset = { x: cursor.x - winX, y: cursor.y - winY };
});

ipcMain.on('window-drag', (_event, screenX, screenY) => {
  if (!mainWindow || !dragOffset) return;
  mainWindow.setPosition(screenX - dragOffset.x, screenY - dragOffset.y);
});

ipcMain.on('window-end-drag', () => {
  dragOffset = null;
});

app.whenReady().then(async () => {
  try {
    await ensureBackendRunning();
  } catch (err) {
    console.error('[startup] backend failed', err);
  }

  createWindow();

  setInterval(() => {
    ensureBackendRunning().catch((err) => {
      console.error('[healthcheck] backend restart failed', err);
    });
  }, 2000);

  app.on('activate', async () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      try {
        await ensureBackendRunning();
      } catch (err) {
        console.error('[activate] backend restart failed', err);
      }
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    stopPythonBackend();
    app.quit();
  }
});

app.on('before-quit', () => {
  stopPythonBackend();
});
