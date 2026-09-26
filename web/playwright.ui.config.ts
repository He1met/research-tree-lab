import config from './playwright.config';
export default { ...config, use: { ...config.use, baseURL: 'http://127.0.0.1:5187' }, webServer: { command: 'npm run dev -- --port 5187 --strictPort', port: 5187, reuseExistingServer: false } };
