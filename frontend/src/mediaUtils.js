export const UPLOAD_MAX_DIMENSION = 1920;
export const UPLOAD_TARGET_BYTES = 700000;
export const EXCEL_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
export const PDF_MIME_TYPE = 'application/pdf';

export function dataUrlByteLength(dataUrl) {
  const base64 = dataUrl.split(',')[1] || '';
  return Math.floor((base64.length * 3) / 4);
}

export function resizeImageDataUrl(dataUrl, maxDimension, targetBytes) {
  return new Promise((resolve) => {
    if (dataUrlByteLength(dataUrl) <= targetBytes) {
      resolve(dataUrl);
      return;
    }
    const source = new Image();
    source.onload = () => {
      const scale = Math.min(1, maxDimension / Math.max(source.naturalWidth, source.naturalHeight));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(source.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(source.naturalHeight * scale));
      const context = canvas.getContext('2d');
      if (!context) {
        resolve(dataUrl);
        return;
      }
      context.drawImage(source, 0, 0, canvas.width, canvas.height);
      let output = dataUrl;
      for (const quality of [0.85, 0.75, 0.65, 0.5, 0.35]) {
        output = canvas.toDataURL('image/jpeg', quality);
        if (dataUrlByteLength(output) <= targetBytes) {
          break;
        }
      }
      resolve(output);
    };
    source.onerror = () => resolve(dataUrl);
    source.src = dataUrl;
  });
}

export function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      const dataUrl = await resizeImageDataUrl(reader.result, UPLOAD_MAX_DIMENSION, UPLOAD_TARGET_BYTES);
      resolve({ name: file.name, dataUrl });
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function base64ToBlob(base64, mimeType) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return new Blob([bytes], { type: mimeType });
}

export function downloadBase64File(base64, mimeType, fileName) {
  if (!base64) return;
  const url = URL.createObjectURL(base64ToBlob(base64, mimeType));
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName || 'download';
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function postJson(url, body) {
  const headers = { 'Content-Type': 'application/json' };
  const appKey = import.meta.env.VITE_APP_ACCESS_KEY;
  if (appKey) {
    headers['X-App-Key'] = appKey;
  }
  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `Request failed: ${response.status}`);
  }
  return payload;
}
