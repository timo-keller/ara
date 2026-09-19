import { registerIconLibrary } from '@synergy-design-system/components/utilities/icon-library.js';

registerIconLibrary('ara', {
  resolver: (name) => `/assets/synergy-icons/${name}.svg`,
});
