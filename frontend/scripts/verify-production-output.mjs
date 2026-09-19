import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const outputDirectory = fileURLToPath(new URL('../dist/ara-frontend/browser/', import.meta.url));

async function filesIn(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(
    entries.map(async (entry) => {
      const path = join(directory, entry.name);
      return entry.isDirectory() ? filesIn(path) : [path];
    }),
  );

  return paths.flat();
}

const files = await filesIn(outputDirectory);
const fileNames = files.map((file) => file.toString());
const output = await Promise.all(files.map((file) => readFile(file, 'utf8').catch(() => '')));
const content = output.join('\n');

const requiredAssets = [
  /SICKIntl-Regular.*\.woff2$/,
  /SICKIntl-Semibold.*\.woff2$/,
  /synergy-icons\/add\.svg$/,
];
const excludedContent = [
  '@synergy-design-system/mcp',
  'syn-mcp',
  'node_modules',
  'https://www.sick.com/media/fonts',
  'FIGMA_TOKEN',
];

for (const asset of requiredAssets) {
  if (!fileNames.some((file) => asset.test(file))) {
    throw new Error(`Missing required local production asset: ${asset}`);
  }
}

for (const value of excludedContent) {
  if (content.includes(value)) {
    throw new Error(`Production output contains excluded content: ${value}`);
  }
}

console.log('Production output contains local Synergy fonts and icons only.');
