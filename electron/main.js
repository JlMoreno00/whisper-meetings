const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');

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
    frame: process.platform !== 'darwin',
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
