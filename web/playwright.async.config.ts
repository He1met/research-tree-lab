import config from './playwright.config';
export default { ...config, use: { ...config.use, baseURL: 'http://127.0.0.1:5188' }, webServer: { command: 'npm run dev -- --port 5188 --strictPort', port: 5188, reuseExistingServer: false } };
