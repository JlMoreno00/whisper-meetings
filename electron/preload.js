const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getWsPort: () => ipcRenderer.invoke('get-ws-port'),
});
