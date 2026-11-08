import { defineConfig } from '@playwright/test';

// 0.26.7.0(2): frame-time measurements depend on the machine – they run in their own projects after every other browser test
// of their engine, never next to busy parallel workers (the functional tests stay fully parallel)
const FRAMES = /house_frames\.spec\.mjs/;
const WEBVIEW = {
  browserName: 'chromium',
  viewport: { width: 412, height: 915 },
  deviceScaleFactor: 2.625,
  isMobile: true,
  hasTouch: true,
  userAgent: 'Mozilla/5.0 (Linux; Android 15; Pixel 8 Build/AP3A.240905.015; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.0.0 Mobile Safari/537.36 Home Assistant/2026.9.1',
};

export default defineConfig({
  testDir: './frontend_tests',
  timeout: 30_000,
  retries: 1,
  reporter: [['line']],
  use: {
    headless: true,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', testIgnore: FRAMES, use: { browserName: 'chromium' } },
    { name: 'webkit', testIgnore: FRAMES, use: { browserName: 'webkit' } },
    { name: 'firefox', testIgnore: FRAMES, use: { browserName: 'firefox' } },
    {
      name: 'android-webview',
      testIgnore: FRAMES,
      use: WEBVIEW,
    },
    // the smoothness of the house map's animation, alone after the functional tests (chromium, then the WebView).
    // 0.26.7.0 UI/theme order: no trace recording while frame times are measured – the trace's screencast and snapshots
    // took enough CPU in the software-rastered sun scenes to push single frames to a third vsync (p95 exactly 50 ms on the
    // unchanged release as well); limit, method and scenes of the measurement are unchanged
    { name: 'frames-chromium', testMatch: FRAMES, dependencies: ['chromium', 'android-webview'], use: { browserName: 'chromium', trace: 'off' } },
    { name: 'frames-android-webview', testMatch: FRAMES, dependencies: ['frames-chromium'], use: { ...WEBVIEW, trace: 'off' } },
  ],
});
