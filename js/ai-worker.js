importScripts('https://cdn.jsdelivr.net/npm/onnxruntime-web@1.19.0/dist/ort.min.js');
let session=null;
let names=['.pessoa','.máquina','operador','objeto'];
self.onmessage = async (e) => {
  const {type, payload} = e.data;
  if (type==='init') {
    try {
      const url = payload.modelUrl || '../../backend/model/edgev1-int8.onnx';
      const alt = '../../backend/model/edgev1.onnx';
      ort.env.wasm.numThreads=1;
      ort.env.wasm.simd=true;
      try { session = await ort.InferenceSession.create(url, {executionProviders:['wasm']}); }
      catch(_) { session = await ort.InferenceSession.create(alt, {executionProviders:['wasm']}); }
      self.postMessage({type:'ready', model: url});
    } catch(err){ self.postMessage({type:'error', message: String(err.message||err)}); }
    return;
  }
  if (type==='infer') {
    if (!session) { self.postMessage({type:'error', message:'Modelo não carregado'}); return; }
    try {
      const {buffer, width, height, cameraId} = payload;
      const inputSize=640;
      const src = new Uint8ClampedArray(buffer);
      const tmp = new OffscreenCanvas(width, height);
      const tctx = tmp.getContext('2d');
      tctx.putImageData(new ImageData(src, width, height), 0, 0);
      const canvas = new OffscreenCanvas(inputSize, inputSize);
      const ctx = canvas.getContext('2d');
      const scale = Math.min(inputSize/width, inputSize/height);
      const nw = Math.round(width*scale), nh=Math.round(height*scale);
      const dx = Math.round((inputSize-nw)/2), dy=Math.round((inputSize-nh)/2);
      ctx.fillStyle='#000'; ctx.fillRect(0,0,inputSize,inputSize);
      ctx.drawImage(tmp, 0, 0, width, height, dx, dy, nw, nh);
      const data = ctx.getImageData(0,0,inputSize,inputSize).data;
      const float = new Float32Array(3*inputSize*inputSize);
      for(let i=0;i<inputSize*inputSize;i++){
        float[i] = data[i*4]/255;
        float[i+inputSize*inputSize] = data[i*4+1]/255;
        float[i+2*inputSize*inputSize] = data[i*4+2]/255;
      }
      const tensor = new ort.Tensor('float32', float, [1,3,inputSize,inputSize]);
      const feeds = {}; feeds[session.inputNames[0]] = tensor;
      const out = await session.run(feeds);
      const output = out[session.outputNames[0]];
      const dims = output.dims;
      const arr = output.data;
      const detections=[];
      const confThr = payload.confidence ?? 0.4;
      const n = dims[1];
      for(let i=0;i<n;i++){
        let x1,y1,x2,y2,score,cls;
        if (dims.length===3 && dims[2]===6){
          const base=i*6;
          x1=arr[base]; y1=arr[base+1]; x2=arr[base+2]; y2=arr[base+3]; score=arr[base+4]; cls=Math.round(arr[base+5]);
        } else { continue; }
        if (score < confThr) continue;
        let raw = (names[cls]||String(cls)).toLowerCase().trim().replace('.','');
        let class_name='other';
        if(['pessoa','human','humano','worker','trabalhador','operador'].includes(raw)) class_name='human';
        else if(['máquina','maquina','machine','vehicle','veiculo','veículo','forklift','empilhadeira','objeto'].includes(raw)) class_name='forklift';
        else if(cls===0) class_name='human';
        else if(cls===1) class_name='forklift';
        else continue;
        const bx=[x1,y1,x2,y2];
        const sx=(bx[0]-dx)/scale, sy=(bx[1]-dy)/scale, sx2=(bx[2]-dx)/scale, sy2=(bx[3]-dy)/scale;
        const bbox=[Math.max(0,sx),Math.max(0,sy),Math.min(width,sx2),Math.min(height,sy2)];
        if(bbox[2]<=bbox[0] || bbox[3]<=bbox[1]) continue;
        detections.push({class_id:cls, class_name, label: raw, confidence: Math.round(score*10000)/10000, bbox: bbox.map(v=>Math.round(v*100)/100), track_id:null});
      }
      self.postMessage({type:'result', cameraId, detections});
    } catch(err){ self.postMessage({type:'error', message: String(err.message||err)}); }
  }
};
