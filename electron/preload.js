const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getWsPort: () => ipcRenderer.invoke('get-ws-port'),
  transcribeFile: (filePath) => ipcRenderer.invoke('transcribe-file', filePath),
  cancelTranscription: () => ipcRenderer.invoke('cancel-transcription'),
  getPathForFile: (file) => webUtils.getPathForFile(file),
  onTranscribeProgress: (callback) => {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('transcribe-progress', handler);
    return () => ipcRenderer.removeListener('transcribe-progress', handler);
  },
  // Programmatic window dragging (bypass app-region CSS issues)
  windowStartDrag: () => ipcRenderer.send('window-start-drag'),
  windowDrag: (screenX, screenY) => ipcRenderer.send('window-drag', screenX, screenY),
  windowEndDrag: () => ipcRenderer.send('window-end-drag'),
});
