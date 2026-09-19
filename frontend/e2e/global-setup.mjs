import { createServer } from 'node:http';
import { generateKeyPairSync, randomUUID, sign } from 'node:crypto';
import { once } from 'node:events';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { parse } from 'node:querystring';

const frontend = resolve(import.meta.dirname, '..');
const repository = resolve(frontend, '..');
const backend = join(repository, 'backend');
const artifacts = join(frontend, 'test-results', 'e2e-services');
const serviceStopTimeout = 10_000;

function start(command, args, options) {
  const child = spawn(command, args, {
    ...options,
    detached: process.platform !== 'win32',
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let output = '';
  child.stdout.on('data', (chunk) => (output += chunk));
  child.stderr.on('data', (chunk) => (output += chunk));
  return { child, output: () => output };
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}

function waitForExit(child) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve();
  return once(child, 'exit');
}

function signalService(child, signal) {
  if (!child.pid) return;
  try {
    if (process.platform === 'win32') child.kill(signal);
    else process.kill(-child.pid, signal);
  } catch (error) {
    if (error.code !== 'ESRCH') throw error;
  }
}

async function stopService(service) {
  if (!service) return;
  const exited = waitForExit(service.child);
  signalService(service.child, 'SIGTERM');
  if (await Promise.race([exited.then(() => true), delay(serviceStopTimeout).then(() => false)])) {
    return;
  }
  signalService(service.child, 'SIGKILL');
  await Promise.race([exited, delay(serviceStopTimeout)]);
  if (service.child.exitCode === null && service.child.signalCode === null) {
    throw new Error(`Service ${service.child.pid} did not exit after SIGKILL`);
  }
}

async function closeServer(server) {
  if (!server?.listening) return;
  const closed = new Promise((resolveClose, rejectClose) =>
    server.close((error) => (error ? rejectClose(error) : resolveClose())),
  );
  server.closeAllConnections?.();
  if (
    !(await Promise.race([closed.then(() => true), delay(serviceStopTimeout).then(() => false)]))
  ) {
    server.closeAllConnections?.();
    throw new Error('OIDC test provider did not close within 10 seconds');
  }
}

function run(command, args, options) {
  return new Promise((resolveRun, reject) => {
    const process = start(command, args, options);
    const timer = setTimeout(() => process.child.kill('SIGKILL'), 60_000);
    process.child.on('exit', (code) => {
      clearTimeout(timer);
      code === 0
        ? resolveRun()
        : reject(new Error(`${command} ${args.join(' ')} failed:\n${process.output()}`));
    });
  });
}

async function port() {
  const server = createServer();
  await new Promise((resolveListen) => server.listen(0, '127.0.0.1', resolveListen));
  const value = server.address().port;
  await new Promise((resolveClose) => server.close(resolveClose));
  return value;
}

async function waitFor(url, service) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(url)).ok) return;
    } catch {}
    await new Promise((resolveWait) => setTimeout(resolveWait, 250));
  }
  throw new Error(`${url} did not start within 30 seconds:\n${service.output()}`);
}

async function oidcProvider(issuer) {
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const jwk = publicKey.export({ format: 'jwk' });
  jwk.kid = 'e2e';
  jwk.use = 'sig';
  jwk.alg = 'RS256';
  const codes = new Map();
  const server = createServer(async (request, response) => {
    const url = new URL(request.url, issuer);
    if (url.pathname === '/.well-known/openid-configuration') {
      return json(response, {
        issuer,
        authorization_endpoint: `${issuer}/authorize`,
        token_endpoint: `${issuer}/token`,
        jwks_uri: `${issuer}/keys`,
      });
    }
    if (url.pathname === '/keys') return json(response, { keys: [jwk] });
    if (url.pathname === '/authorize') {
      const identity =
        /e2e_identity=([^;]+)/.exec(request.headers.cookie || '')?.[1] || 'alpha-user';
      const code = randomUUID();
      codes.set(code, { identity, nonce: url.searchParams.get('nonce') });
      const callback = new URL(url.searchParams.get('redirect_uri'));
      callback.searchParams.set('code', code);
      callback.searchParams.set('state', url.searchParams.get('state'));
      response.writeHead(302, { location: callback.toString() });
      return response.end();
    }
    if (url.pathname === '/token' && request.method === 'POST') {
      let body = '';
      for await (const chunk of request) body += chunk;
      const ticket = codes.get(parse(body).code);
      if (!ticket) return json(response, { error: 'invalid_grant' }, 400);
      const groups =
        ticket.identity === 'alpha-admin'
          ? ['alpha-admin']
          : ticket.identity === 'bravo-user'
            ? ['bravo-user']
            : ['alpha-user'];
      const now = Math.floor(Date.now() / 1000);
      const header = Buffer.from(JSON.stringify({ alg: 'RS256', kid: 'e2e', typ: 'JWT' })).toString(
        'base64url',
      );
      const payload = Buffer.from(
        JSON.stringify({
          iss: issuer,
          aud: 'ara-e2e',
          sub: ticket.identity,
          name: ticket.identity,
          groups,
          nonce: ticket.nonce,
          iat: now,
          exp: now + 300,
        }),
      ).toString('base64url');
      const signature = sign(
        'RSA-SHA256',
        Buffer.from(`${header}.${payload}`),
        privateKey,
      ).toString('base64url');
      return json(response, {
        id_token: `${header}.${payload}.${signature}`,
        token_type: 'Bearer',
      });
    }
    response.writeHead(404);
    response.end();
  });
  await new Promise((resolveListen) =>
    server.listen(Number(new URL(issuer).port), '127.0.0.1', resolveListen),
  );
  return server;
}

function json(response, value, status = 200) {
  response.writeHead(status, { 'content-type': 'application/json' });
  response.end(JSON.stringify(value));
}

export default async function setup() {
  const temp = await mkdtemp(join(tmpdir(), 'ara-e2e-'));
  let api;
  let web;
  let oidc;
  let frontendUrl;
  const cleanup = async () => {
    await Promise.allSettled([stopService(web), stopService(api), closeServer(oidc)]);
    try {
      await mkdir(artifacts, { recursive: true });
      await Promise.all([
        writeFile(join(artifacts, 'backend.log'), api?.output() ?? ''),
        writeFile(join(artifacts, 'frontend.log'), web?.output() ?? ''),
      ]);
    } finally {
      await rm(temp, { recursive: true, force: true });
    }
  };
  try {
    const backendPort = await port();
    const frontendPort = await port();
    const oidcPort = await port();
    const databaseUrl = `sqlite+aiosqlite:///${join(temp, 'ara.db')}`;
    frontendUrl = `http://localhost:${frontendPort}`;
    const issuer = `http://localhost:${oidcPort}`;
    const environment = {
      ...process.env,
      ARA_DATABASE_URL: databaseUrl,
      ARA_PUBLIC_URL: frontendUrl,
      ARA_OIDC_ISSUER_URL: issuer,
      ARA_OIDC_CLIENT_ID: 'ara-e2e',
      ARA_OIDC_CLIENT_SECRET: 'e2e-client-secret',
      ARA_SESSION_SECRET: 'e2e-session-secret',
      ARA_OWNER_SUBJECTS: 'e2e-owner',
    };
    await run('uv', ['run', 'alembic', 'upgrade', 'head'], { cwd: backend, env: environment });
    await run('uv', ['run', 'python', 'e2e/seed.py', databaseUrl, issuer], {
      cwd: backend,
      env: environment,
    });
    oidc = await oidcProvider(issuer);
    api = start(
      'uv',
      ['run', 'uvicorn', 'ara.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
      { cwd: backend, env: environment },
    );
    await waitFor(`http://127.0.0.1:${backendPort}/`, api);
    const proxy = join(temp, 'proxy.json');
    await writeFile(
      proxy,
      JSON.stringify({
        '/api': { target: `http://127.0.0.1:${backendPort}`, secure: false },
        '/auth': { target: `http://127.0.0.1:${backendPort}`, secure: false },
      }),
    );
    web = start(
      process.execPath,
      [
        join(frontend, 'node_modules', '@angular', 'cli', 'bin', 'ng.js'),
        'serve',
        '--host',
        'localhost',
        '--port',
        String(frontendPort),
        '--proxy-config',
        proxy,
      ],
      { cwd: frontend, env: environment },
    );
    await waitFor(frontendUrl, web);
  } catch (error) {
    await cleanup();
    throw error;
  }
  process.env.ARA_E2E_URL = frontendUrl;
  return cleanup;
}
