import { API_PATH, AUTH_PATH } from './runtime-paths';

describe('runtime paths', () => {
  it('uses same-origin API and authentication paths', () => {
    expect(API_PATH).toBe('/api');
    expect(AUTH_PATH).toBe('/auth');
  });
});
