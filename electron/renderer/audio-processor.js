class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = [];
    this._targetRate = 16000;
    this._frameSize = 320; // 20ms at 16kHz
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0];
    const ratio = this._targetRate / sampleRate;

    for (let i = 0; i < samples.length; i++) {
      const idx = Math.floor(i * ratio);
      if (idx !== Math.floor((i - 1) * ratio) || i === 0) {
        const clamped = Math.max(-1, Math.min(1, samples[i]));
        this._buffer.push(clamped * 0x7fff | 0);
      }
    }

    while (this._buffer.length >= this._frameSize) {
      const frame = new Int16Array(this._buffer.splice(0, this._frameSize));
      this.port.postMessage(frame.buffer, [frame.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
