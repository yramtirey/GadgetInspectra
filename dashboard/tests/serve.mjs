// Serve the production artifact at the exact Pages subpath during regression tests.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';

const root = resolve('dist');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
createServer(async (request, response) => {
  const pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  if (!pathname.startsWith('/GadgetInspectra/')) { response.writeHead(404).end(); return; }
  const file = resolve(root, pathname.slice('/GadgetInspectra/'.length) || 'index.html');
  if (!file.startsWith(root + '/')) { response.writeHead(404).end(); return; }
  try {
    const data = await readFile(file);
    response.writeHead(200, { 'Content-Type': types[extname(file)] || 'application/octet-stream' }).end(data);
  } catch { response.writeHead(404).end(); }
}).listen(4173, '127.0.0.1');
